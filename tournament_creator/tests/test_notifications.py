import json
import smtplib
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from tournament_creator.models.auth import User
from tournament_creator.models.logging import MatchResultLog
from tournament_creator.models.notifications import NotificationBackendSetting, NotificationLog
from tournament_creator.models.base_models import Matchup, TournamentChart, Player, Pair # TournamentChart is here
from tournament_creator.forms import EmailBackendConfigForm
import requests # For requests.exceptions

# Functions to test
from tournament_creator.notifications import send_email_notification, send_signal_notification


class TestSendEmailNotification(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        # Tournament created here will be updated in tests for notification flags
        self.tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2024-01-01',
            number_of_rounds=3,
            number_of_courts=1
        )
        
        self.player1 = Player.objects.create(first_name='Alice', last_name='Smith', ranking=1)
        self.player2 = Player.objects.create(first_name='Bob', last_name='Johnson', ranking=2)
        self.player3 = Player.objects.create(first_name='Charlie', last_name='Brown', ranking=3)
        self.player4 = Player.objects.create(first_name='Diana', last_name='Prince', ranking=4)

        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1, court_number=1,
            pair1_player1=self.player1, pair1_player2=self.player2,
            pair2_player1=self.player3, pair2_player2=self.player4,
        )
        self.match_log = MatchResultLog.objects.create(
            matchup=self.matchup, recorded_by=self.user, action='CREATE',
            details={'team1_scores': [21, 15], 'team2_scores': [19, 10], 'winning_team': 'team1'}
        )
        self.email_config = {
            'recipient_list': "test1@example.com, test2@example.com",
            'from_email': 'noreply@example.com', 'host': 'smtp.example.com', 'port': 587,
            'username': 'user', 'password': 'password', 'use_tls': True, 'use_ssl': False,
        }
        NotificationLog.objects.all().delete() # Clear logs before each test method in this class

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_sent_successfully(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        mock_backend_instance.send_messages.return_value = 1
        mock_smtp_backend_class.return_value = mock_backend_instance

        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=self.email_config
        )
        self.tournament.notify_by_email = True # Ensure per-tournament is active
        self.tournament.save()

        send_email_notification(self.user, self.match_log, self.tournament)

        mock_smtp_backend_class.assert_called_once_with(
            host=self.email_config['host'], port=self.email_config['port'],
            username=self.email_config['username'], password=self.email_config['password'],
            use_tls=self.email_config['use_tls'], use_ssl=self.email_config['use_ssl'],
            fail_silently=False
        )
        self.assertTrue(mock_backend_instance.send_messages.called)
        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertTrue(log_entry.success)

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_skipped_tournament_inactive(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        mock_smtp_backend_class.return_value = mock_backend_instance
        
        active_email_setting = NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=self.email_config
        )
        self.tournament.notify_by_email = False # Tournament setting disables email
        self.tournament.save()

        send_email_notification(self.user, self.match_log, self.tournament)

        mock_backend_instance.send_messages.assert_not_called()
        log_entry = NotificationLog.objects.filter(backend_setting=active_email_setting).latest('timestamp')
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertIn(f"Email notification skipped for tournament '{self.tournament.name}' as per tournament settings (disabled).", log_entry.details)
        self.assertEqual(log_entry.backend_setting, active_email_setting)

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_sending_fails_smtp_error(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        mock_backend_instance.send_messages.side_effect = smtplib.SMTPException("Test SMTP Error")
        mock_smtp_backend_class.return_value = mock_backend_instance
        
        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=self.email_config
        )
        self.tournament.notify_by_email = True # Global fail, tournament active
        self.tournament.save()

        send_email_notification(self.user, self.match_log, self.tournament)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertIn("SMTP Error: Test SMTP Error", log_entry.details)

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_no_active_email_backend(self, mock_smtp_backend_class):
        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=False, config=self.email_config
        )
        self.tournament.notify_by_email = True # Global fail, tournament active
        self.tournament.save()
        
        send_email_notification(self.user, self.match_log, self.tournament)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertIn("Email backend 'email' not found or is not active globally.", log_entry.details)
        mock_smtp_backend_class.assert_not_called()

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_backend_misconfigured_no_recipients(self, mock_smtp_backend_class):
        incomplete_config = self.email_config.copy()
        incomplete_config['recipient_list'] = "" # Empty recipient_list
        
        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=incomplete_config
        )
        self.tournament.notify_by_email = True # Global config fail, tournament active
        self.tournament.save()

        send_email_notification(self.user, self.match_log, self.tournament)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertIn("Failed to send email: No recipients found in configuration", log_entry.details)
        mock_smtp_backend_class.assert_not_called()

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_backend_no_config_object(self, mock_smtp_backend_class):
        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=None # Config is None
        )
        self.tournament.notify_by_email = True
        self.tournament.save()

        send_email_notification(self.user, self.match_log, self.tournament)
        log_entry = NotificationLog.objects.first()
        self.assertFalse(log_entry.success)
        self.assertIn("Email backend 'email' is active but has no configuration.", log_entry.details)
        mock_smtp_backend_class.assert_not_called()


class TestSendSignalNotification(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='signaluser', password='password')
        self.tournament = TournamentChart.objects.create(
            name='Signal Test Tournament',
            date='2024-03-01',
            number_of_rounds=3,
            number_of_courts=1
        )
        
        self.player1 = Player.objects.create(first_name='SignalP1', last_name='UserA', ranking=10)
        self.player2 = Player.objects.create(first_name='SignalP2', last_name='UserB', ranking=11)
        self.player3 = Player.objects.create(first_name='SignalP3', last_name='UserC', ranking=12)
        self.player4 = Player.objects.create(first_name='SignalP4', last_name='UserD', ranking=13)

        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament, round_number=1, court_number=1,
            pair1_player1=self.player1, pair1_player2=self.player2,
            pair2_player1=self.player3, pair2_player2=self.player4,
        )
        self.match_log = MatchResultLog.objects.create(
            matchup=self.matchup, recorded_by=self.user, action='UPDATE',
            details={'team1_scores': [25], 'team2_scores': [23], 'winning_team': 'team1'}
        )
        self.base_signal_config = {
            'signal_cli_rest_api_url': 'http://localhost:8080',
            'signal_sender_phone_number': '+10000000000',
            'recipient_usernames': '', 'recipient_group_ids': ''
        }
        NotificationLog.objects.all().delete()

    def _create_signal_setting(self, is_active=True, config_override=None):
        NotificationBackendSetting.objects.filter(backend_name='signal').delete()
        current_config = self.base_signal_config.copy()
        if config_override:
            current_config.update(config_override)
        return NotificationBackendSetting.objects.create(
            backend_name='signal', is_active=is_active, config=current_config
        )

    @patch('tournament_creator.notifications.requests.post')
    def test_successful_send_with_usernames(self, mock_post):
        mock_response = MagicMock(status_code=201, text='{"message": "Accepted"}')
        mock_response.json.return_value = {"message": "Accepted"}
        mock_post.return_value = mock_response

        config_override = {'recipient_usernames': '+111,+122'}
        self._create_signal_setting(config_override=config_override)
        self.tournament.notify_by_signal = True
        self.tournament.save()

        send_signal_notification(self.user, self.match_log, self.tournament)

        mock_post.assert_called_once()
        log_entry = NotificationLog.objects.first()
        self.assertTrue(log_entry.success)
        self.assertIn("Usernames: +111, +122", log_entry.details)

    @patch('tournament_creator.notifications.requests.post')
    def test_signal_skipped_tournament_inactive(self, mock_post):
        active_signal_setting = self._create_signal_setting(config_override={'recipient_usernames': '+111'})
        self.tournament.notify_by_signal = False # Tournament setting disables signal
        self.tournament.save()

        send_signal_notification(self.user, self.match_log, self.tournament)

        mock_post.assert_not_called()
        log_entry = NotificationLog.objects.filter(backend_setting=active_signal_setting).latest('timestamp')
        self.assertFalse(log_entry.success)
        self.assertIn(f"Signal notification skipped for tournament '{self.tournament.name}' as per tournament settings (disabled).", log_entry.details)
        self.assertEqual(log_entry.backend_setting, active_signal_setting)

    @patch('tournament_creator.notifications.requests.post')
    def test_signal_backend_not_active(self, mock_post):
        self._create_signal_setting(is_active=False, config_override={'recipient_usernames': '+111'})
        self.tournament.notify_by_signal = True # Global fail, tournament active
        self.tournament.save()
        send_signal_notification(self.user, self.match_log, self.tournament)
        mock_post.assert_not_called()
        log = NotificationLog.objects.first()
        self.assertFalse(log.success)
        self.assertIn("Signal backend 'signal' not found or is not active globally.", log.details)

    @patch('tournament_creator.notifications.requests.post')
    def test_signal_backend_missing_url(self, mock_post):
        config_override = self.base_signal_config.copy()
        del config_override['signal_cli_rest_api_url']
        config_override['recipient_usernames'] = '+111'
        self._create_signal_setting(config_override=config_override)
        self.tournament.notify_by_signal = True
        self.tournament.save()
        send_signal_notification(self.user, self.match_log, self.tournament)
        mock_post.assert_not_called()
        log = NotificationLog.objects.first()
        self.assertFalse(log.success)
        self.assertIn("configuration is missing 'signal_cli_rest_api_url' or 'signal_sender_phone_number'", log.details)

    @patch('tournament_creator.notifications.requests.post')
    def test_api_http_error_400_json_response(self, mock_post):
        mock_response = MagicMock(status_code=400, text='{"error": "Bad API request"}')
        mock_response.json.return_value = {"error": "Bad API request"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        
        self._create_signal_setting(config_override={'recipient_usernames': '+111'})
        self.tournament.notify_by_signal = True
        self.tournament.save()
        send_signal_notification(self.user, self.match_log, self.tournament)
        
        mock_post.assert_called_once()
        log = NotificationLog.objects.first()
        self.assertFalse(log.success)
        self.assertIn("Signal API HTTP Error: 400", log.details)
        self.assertIn("API Error Message: Bad API request", log.details)


class TestNotificationTriggerInView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testadmin', password='password', role=User.Role.ADMIN)
        self.client.force_login(self.user)

        # Tournament will have default notification flags (False) unless explicitly set
        self.tournament = TournamentChart.objects.create(
            name='Trigger Test Tournament',
            date='2024-01-02',
            number_of_rounds=3,
            number_of_courts=1
        )
        self.player1 = Player.objects.create(first_name='P1', last_name='Test', ranking=1)
        self.player2 = Player.objects.create(first_name='P2', last_name='Test', ranking=2)
        self.player3 = Player.objects.create(first_name='P3', last_name='Test', ranking=3)
        self.player4 = Player.objects.create(first_name='P4', last_name='Test', ranking=4)

        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament, round_number=1, court_number=1,
            pair1_player1=self.player1, pair1_player2=self.player2,
            pair2_player1=self.player3, pair2_player2=self.player4
        )
        
        NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True,
            config={'recipient_list': ['notify@example.com'], 'from_email': 'system@example.com',
                    'host': 'smtp.example.com', 'port': 587, 'use_tls': True}
        )
        NotificationBackendSetting.objects.create(
            backend_name='signal', is_active=True,
            config={'signal_cli_rest_api_url': 'http://localhost:9090', 
                    'signal_sender_phone_number': '+19998887777', 
                    'recipient_usernames': '+16665554444'}
        )
        self.record_url = reverse('record_match_result', args=[self.tournament.id, self.matchup.id])
        NotificationLog.objects.all().delete()


    @patch('tournament_creator.views.tournament_views.send_signal_notification') # Mock at source of call
    @patch('tournament_creator.views.tournament_views.send_email_notification') # Mock at source of call
    def test_notifications_called_when_tournament_flags_true(self, mock_send_email, mock_send_signal):
        self.tournament.notify_by_email = True
        self.tournament.notify_by_signal = True
        self.tournament.save()

        score_data = {'team1_scores': json.dumps([21]), 'team2_scores': json.dumps([19])}
        response = self.client.post(self.record_url, data=score_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        self.assertTrue(MatchResultLog.objects.filter(matchup=self.matchup).exists())
        match_log_entry = MatchResultLog.objects.get(matchup=self.matchup)
        
        mock_send_email.assert_called_once_with(
            user_who_recorded=self.user,
            match_result_log_instance=match_log_entry,
            tournament_chart_instance=self.tournament
        )
        mock_send_signal.assert_called_once_with(
            user_who_recorded=self.user,
            match_result_log_instance=match_log_entry,
            tournament_chart_instance=self.tournament
        )

    @patch('tournament_creator.views.tournament_views.send_signal_notification')
    @patch('tournament_creator.views.tournament_views.send_email_notification')
    def test_notifications_not_called_when_tournament_flags_false(self, mock_send_email, mock_send_signal):
        self.tournament.notify_by_email = False # Explicitly false
        self.tournament.notify_by_signal = False # Explicitly false
        self.tournament.save()

        score_data = {'team1_scores': json.dumps([21]), 'team2_scores': json.dumps([19])}
        response = self.client.post(self.record_url, data=score_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # Notification functions in notifications.py will log the skip,
        # but the view itself still calls them. The functions then return early.
        # So, we expect them to be called by the view.
        self.assertTrue(MatchResultLog.objects.filter(matchup=self.matchup).exists())
        match_log_entry = MatchResultLog.objects.get(matchup=self.matchup)

        mock_send_email.assert_called_once_with(
            user_who_recorded=self.user,
            match_result_log_instance=match_log_entry,
            tournament_chart_instance=self.tournament
        )
        mock_send_signal.assert_called_once_with(
            user_who_recorded=self.user,
            match_result_log_instance=match_log_entry,
            tournament_chart_instance=self.tournament
        )
        
        # Verify that NotificationLog entries show these were skipped due to tournament settings
        # This requires the actual notification functions to run, so we can't fully mock them here
        # if we want to test the log entries they create.
        # For this specific test, we are only checking if the view *calls* them.
        # The tests in TestSendEmailNotification and TestSendSignalNotification cover the internal logic.


    @patch('tournament_creator.views.tournament_views.send_signal_notification')
    @patch('tournament_creator.views.tournament_views.send_email_notification')
    def test_notification_not_sent_on_invalid_score_submission(self, mock_send_email, mock_send_signal):
        self.tournament.notify_by_email = True # Enable for test
        self.tournament.notify_by_signal = True
        self.tournament.save()

        invalid_score_data = {'team1_scores': json.dumps([21])} # Missing team2_scores
        response = self.client.post(self.record_url, data=invalid_score_data)
        
        self.assertEqual(response.json()['status'], 'error')
        mock_send_email.assert_not_called()
        mock_send_signal.assert_not_called()

# Admin view tests remain largely unchanged by this feature, 
# but are kept for completeness of the file.
class TestNotificationAdminViews(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='superadmin', email='super@admin.com', password='password')
        self.client.force_login(self.admin_user)

    def test_notificationbackendsetting_list_view_accessible(self):
        url = reverse('admin:tournament_creator_notificationbackendsetting_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationbackendsetting_add_view_shows_raw_config(self):
        url = reverse('admin:tournament_creator_notificationbackendsetting_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="config"')
        self.assertNotContains(response, 'name="recipient_list"')

    def test_notificationbackendsetting_change_view_non_email_shows_raw_config(self):
        setting = NotificationBackendSetting.objects.create(
            backend_name='matrix', is_active=True, 
            config={'server_url': 'https://matrix.example.com'}
        )
        url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="config"')
        self.assertContains(response, 'https://matrix.example.com')
        self.assertNotContains(response, 'name="recipient_list"')

    def test_notificationbackendsetting_change_view_email_shows_custom_form(self):
        initial_email_config = {
            'recipient_list': 'admin@example.com', 'from_email': 'system@example.org',
            'host': 'smtp.example.org', 'port': 587, 'username': 'emailuser',
            'password': 'securepassword123', 'use_tls': True, 'use_ssl': False
        }
        setting = NotificationBackendSetting.objects.create(
            backend_name='email', is_active=True, config=initial_email_config
        )
        url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for field_name in EmailBackendConfigForm.base_fields.keys():
            self.assertContains(response, f'name="{field_name}"')
        self.assertContains(response, initial_email_config['recipient_list'])
        self.assertNotContains(response, initial_email_config['password'])

    # ... (other admin tests from the original file can be kept as they are mostly unaffected) ...
    def test_notificationlog_list_view_accessible(self):
        url = reverse('admin:tournament_creator_notificationlog_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationlog_change_view_accessible(self):
        setting = NotificationBackendSetting.objects.create(backend_name='log_email', is_active=True)
        tournament = TournamentChart.objects.create(
            name='Log Test Tournament',
            date='2024-01-03',
            number_of_rounds=3,
            number_of_courts=1
        )
        matchup = Matchup.objects.create(tournament_chart=tournament, round_number=1, court_number=1)
        # MatchResultLog is required for NotificationLog if it's not nullable
        mr_log = MatchResultLog.objects.create(matchup=matchup, recorded_by=self.admin_user, action="CREATE", details={})
        log = NotificationLog.objects.create(backend_setting=setting, success=True, match_result_log=mr_log)
        
        url = reverse('admin:tournament_creator_notificationlog_change', args=[log.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
