import json
import smtplib
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from tournament_creator.models.auth import User
from tournament_creator.models.logging import MatchResultLog
from tournament_creator.models.notifications import NotificationBackendSetting, NotificationLog
from tournament_creator.models.base_models import Matchup, TournamentChart, Player, Pair

from tournament_creator.notifications import send_email_notification # The function to test

class TestSendEmailNotification(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.tournament = TournamentChart.objects.create(name='Test Tournament', date='2024-01-01')
        
        # Create players for the matchup
        self.player1 = Player.objects.create(first_name='Alice', last_name='Smith', ranking=1)
        self.player2 = Player.objects.create(first_name='Bob', last_name='Johnson', ranking=2)
        self.player3 = Player.objects.create(first_name='Charlie', last_name='Brown', ranking=3)
        self.player4 = Player.objects.create(first_name='Diana', last_name='Prince', ranking=4)

        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.player1,
            pair1_player2=self.player2,
            pair2_player1=self.player3,
            pair2_player2=self.player4,
        )
        self.match_log = MatchResultLog.objects.create(
            matchup=self.matchup,
            recorded_by=self.user,
            action='CREATE',
            details={'team1_scores': [21, 15], 'team2_scores': [19, 10], 'winning_team': 'team1'}
        )
        self.email_config = {
            'recipient_list': ['test@example.com'],
            'from_email': 'noreply@example.com',
            'host': 'smtp.example.com',
            'port': 587,
            'username': 'user',
            'password': 'password',
            'use_tls': True,
            'use_ssl': False,
        }

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_sent_successfully(self, mock_smtp_backend_class):
        # Configure the mock SMTPEmailBackend instance and its send_messages method
        mock_backend_instance = MagicMock()
        mock_backend_instance.send_messages.return_value = 1 # Simulate one email sent
        mock_smtp_backend_class.return_value = mock_backend_instance # Mock SMTPEmailBackend() constructor

        NotificationBackendSetting.objects.create(
            backend_name='email',
            is_active=True,
            config=self.email_config
        )

        send_email_notification(self.user, self.match_log)

        # Assert SMTPEmailBackend was instantiated with correct parameters
        mock_smtp_backend_class.assert_called_once_with(
            host=self.email_config['host'],
            port=self.email_config['port'],
            username=self.email_config['username'],
            password=self.email_config['password'],
            use_tls=self.email_config['use_tls'],
            use_ssl=self.email_config['use_ssl'],
            fail_silently=False
        )
        
        # Assert send_messages was called (implicitly, as it's part of send_mail)
        # For send_mail, it constructs an EmailMessage and calls send_messages on the backend.
        # We check if the backend's send_messages method was called.
        self.assertTrue(mock_backend_instance.send_messages.called)
        self.assertEqual(mock_backend_instance.send_messages.call_count, 1)
        
        # Assert NotificationLog entry
        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertTrue(log_entry.success)
        self.assertEqual(NotificationLog.objects.count(), 1)
        self.assertIn(self.email_config['recipient_list'][0], log_entry.details)

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_sending_fails_smtp_error(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        # Configure the mock to raise SMTPException when send_messages is called
        mock_backend_instance.send_messages.side_effect = smtplib.SMTPException("Test SMTP Error")
        mock_smtp_backend_class.return_value = mock_backend_instance
        
        NotificationBackendSetting.objects.create(
            backend_name='email',
            is_active=True,
            config=self.email_config
        )

        send_email_notification(self.user, self.match_log)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertEqual(NotificationLog.objects.count(), 1)
        self.assertIn("SMTP Error: Test SMTP Error", log_entry.details)

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_no_active_email_backend(self, mock_smtp_backend_class):
        # Ensure no active 'email' backend exists (either none or is_active=False)
        NotificationBackendSetting.objects.create(
            backend_name='email',
            is_active=False, # Not active
            config=self.email_config
        )
        
        send_email_notification(self.user, self.match_log)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertEqual(NotificationLog.objects.count(), 1)
        self.assertIn("Email backend 'email' not found or is not active.", log_entry.details)
        
        # Assert SMTPEmailBackend was NOT called
        mock_smtp_backend_class.assert_not_called()

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_backend_misconfigured(self, mock_smtp_backend_class):
        incomplete_config = self.email_config.copy()
        del incomplete_config['recipient_list'] # Missing recipient_list
        
        NotificationBackendSetting.objects.create(
            backend_name='email',
            is_active=True,
            config=incomplete_config
        )

        send_email_notification(self.user, self.match_log)

        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertFalse(log_entry.success)
        self.assertEqual(NotificationLog.objects.count(), 1)
        self.assertIn("Email backend 'email' configuration is missing 'recipient_list'.", log_entry.details)

        # Assert SMTPEmailBackend was NOT called
        mock_smtp_backend_class.assert_not_called()

# Tests for Notification Trigger in record_match_result View
class TestNotificationTriggerInView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testadmin', password='password', role=User.Role.ADMIN)
        self.client.force_login(self.user)
        
        self.tournament = TournamentChart.objects.create(name='Trigger Test Tournament', date='2024-01-02')
        self.player1 = Player.objects.create(first_name='P1', last_name='Test', ranking=1)
        self.player2 = Player.objects.create(first_name='P2', last_name='Test', ranking=2)
        self.player3 = Player.objects.create(first_name='P3', last_name='Test', ranking=3)
        self.player4 = Player.objects.create(first_name='P4', last_name='Test', ranking=4)

        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.player1,
            pair1_player2=self.player2,
            pair2_player1=self.player3,
            pair2_player2=self.player4
        )
        
        # Active email backend setting
        NotificationBackendSetting.objects.create(
            backend_name='email',
            is_active=True,
            config={
                'recipient_list': ['notify@example.com'],
                'from_email': 'system@example.com',
                'host': 'smtp.example.com', 'port': 587, 'use_tls': True
            }
        )
        self.record_url = reverse('record_match_result', args=[self.tournament.id, self.matchup.id])

    @patch('tournament_creator.views.tournament_views.send_email_notification')
    def test_notification_sent_on_valid_score_submission(self, mock_send_email):
        score_data = {
            'team1_scores': json.dumps([21, 18]),
            'team2_scores': json.dumps([19, 21]) 
        }
        response = self.client.post(self.record_url, data=score_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        mock_send_email.assert_called_once()
        # Check that a MatchResultLog entry was created
        self.assertTrue(MatchResultLog.objects.filter(matchup=self.matchup).exists())
        match_log_entry = MatchResultLog.objects.get(matchup=self.matchup)
        
        # Check call arguments for mock_send_email
        args, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs['user_who_recorded'], self.user)
        self.assertEqual(kwargs['match_result_log_instance'], match_log_entry)

    @patch('tournament_creator.views.tournament_views.send_email_notification')
    def test_notification_not_sent_on_invalid_score_submission(self, mock_send_email):
        invalid_score_data = { # Missing team2_scores
            'team1_scores': json.dumps([21])
        }
        response = self.client.post(self.record_url, data=invalid_score_data)
        
        self.assertEqual(response.status_code, 200) # View returns 200 even on error, but with error status
        self.assertEqual(response.json()['status'], 'error')
        
        mock_send_email.assert_not_called()

# Tests for Admin Views
class TestNotificationAdminViews(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='superadmin', email='super@admin.com', password='password')
        self.client.force_login(self.admin_user)

    def test_notificationbackendsetting_list_view_accessible(self):
        url = reverse('admin:tournament_creator_notificationbackendsetting_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationlog_list_view_accessible(self):
        url = reverse('admin:tournament_creator_notificationlog_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationbackendsetting_add_view_accessible(self):
        url = reverse('admin:tournament_creator_notificationbackendsetting_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationbackendsetting_change_view_accessible(self):
        setting = NotificationBackendSetting.objects.create(backend_name='test_email', is_active=True, config={})
        url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notificationlog_change_view_accessible(self):
        # Need a backend setting first for the log
        setting = NotificationBackendSetting.objects.create(backend_name='log_email', is_active=True)
        tournament = TournamentChart.objects.create(name='Log Test Tournament', date='2024-01-03')
        matchup = Matchup.objects.create(tournament_chart=tournament, round_number=1, court_number=1)
        log = NotificationLog.objects.create(backend_setting=setting, success=True, match_result_log=None)
        
        url = reverse('admin:tournament_creator_notificationlog_change', args=[log.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
