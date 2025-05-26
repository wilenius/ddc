import json
import smtplib
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from tournament_creator.models.auth import User
from tournament_creator.models.logging import MatchResultLog
from tournament_creator.models.notifications import NotificationBackendSetting, NotificationLog
from tournament_creator.models.base_models import Matchup, TournamentChart, Player, Pair
from tournament_creator.forms import EmailBackendConfigForm # Added import

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
            'recipient_list': "test1@example.com, test2@example.com", # Changed to string
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

        # Check that the recipient list passed to the email backend was correctly parsed
        # send_messages is called with a list of EmailMessage objects
        sent_messages = mock_backend_instance.send_messages.call_args[0][0]
        self.assertEqual(len(sent_messages), 1) # Assuming one message object
        email_message = sent_messages[0]
        self.assertEqual(email_message.to, ['test1@example.com', 'test2@example.com'])
        
        # Assert NotificationLog entry
        log_entry = NotificationLog.objects.first()
        self.assertIsNotNone(log_entry)
        self.assertTrue(log_entry.success)
        self.assertEqual(NotificationLog.objects.count(), 1)
        # The details log should contain the string representation of the parsed list
        self.assertIn('test1@example.com, test2@example.com', log_entry.details)

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
        del incomplete_config['recipient_list'] # Missing recipient_list (None value)
        
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
        # Updated expected message based on new logic in send_email_notification
        self.assertIn("Failed to send email: No recipients found in configuration after parsing or recipient_list is empty.", log_entry.details)

        # Assert SMTPEmailBackend was NOT called
        mock_smtp_backend_class.assert_not_called()

    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_email_sending_fails_no_valid_recipients(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        mock_smtp_backend_class.return_value = mock_backend_instance

        invalid_recipient_lists = [
            "",          # Empty string
            ", , ",      # String with only commas/whitespace
            "   ",       # String with only whitespace
            None,        # None value for recipient_list (though config.get would handle this)
            [],          # Explicitly an empty list if robust parsing handles it
        ]

        for i, invalid_list_val in enumerate(invalid_recipient_lists):
            with self.subTest(invalid_list_val=invalid_list_val, test_run=i):
                NotificationLog.objects.all().delete() # Clean up logs from previous subtest runs
                
                current_config = self.email_config.copy()
                current_config['recipient_list'] = invalid_list_val
                
                # Ensure there's only one setting for this test run
                NotificationBackendSetting.objects.all().delete()
                NotificationBackendSetting.objects.create(
                    backend_name='email',
                    is_active=True,
                    config=current_config
                )

                send_email_notification(self.user, self.match_log)

                log_entry = NotificationLog.objects.first()
                self.assertIsNotNone(log_entry)
                self.assertFalse(log_entry.success)
                self.assertEqual(NotificationLog.objects.count(), 1)
                self.assertIn("Failed to send email: No recipients found in configuration after parsing or recipient_list is empty.", log_entry.details)
                
                # Assert SMTPEmailBackend was NOT called
                mock_backend_instance.send_messages.assert_not_called()
                # Reset mock for next subtest if needed, though it's re-patched per test method
                mock_backend_instance.reset_mock() 
                mock_smtp_backend_class.reset_mock()


    @patch('tournament_creator.notifications.SMTPEmailBackend')
    def test_recipient_list_parsing_edge_cases(self, mock_smtp_backend_class):
        mock_backend_instance = MagicMock()
        mock_backend_instance.send_messages.return_value = 1
        mock_smtp_backend_class.return_value = mock_backend_instance

        test_cases = {
            "trailing_comma": ("test1@example.com,", ['test1@example.com']),
            "leading_comma": (",test1@example.com", ['test1@example.com']),
            "multiple_commas": ("test1@example.com, ,, test2@example.com", ['test1@example.com', 'test2@example.com']),
            "mixed_spacing": ("  test1@example.com  ,test2@example.com,  test3@example.com ", ['test1@example.com', 'test2@example.com', 'test3@example.com']),
            "already_list_robustness": ([" test1@example.com ", "test2@example.com"], ['test1@example.com', 'test2@example.com'])
        }

        for test_name, (recipient_str, expected_list) in test_cases.items():
            with self.subTest(test_name=test_name):
                NotificationLog.objects.all().delete()
                NotificationBackendSetting.objects.all().delete()
                
                current_config = self.email_config.copy()
                current_config['recipient_list'] = recipient_str
                
                NotificationBackendSetting.objects.create(
                    backend_name='email',
                    is_active=True,
                    config=current_config
                )

                send_email_notification(self.user, self.match_log)

                self.assertTrue(mock_backend_instance.send_messages.called)
                sent_messages = mock_backend_instance.send_messages.call_args[0][0]
                self.assertEqual(len(sent_messages), 1)
                email_message = sent_messages[0]
                self.assertEqual(email_message.to, expected_list)
                
                log_entry = NotificationLog.objects.first()
                self.assertIsNotNone(log_entry)
                self.assertTrue(log_entry.success)
                # The details log should contain the string representation of the parsed list
                self.assertIn(', '.join(expected_list), log_entry.details)

                mock_backend_instance.reset_mock()
                mock_smtp_backend_class.reset_mock()


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

    # New tests for admin customization
    def test_notificationbackendsetting_add_view_shows_raw_config(self):
        url = reverse('admin:tournament_creator_notificationbackendsetting_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="config"', msg_prefix="Add view should contain raw config textarea")
        # Check that email form specific fields are NOT present
        self.assertNotContains(response, 'name="recipient_list"', msg_prefix="Add view should not contain email form fields")

    def test_notificationbackendsetting_change_view_non_email_shows_raw_config(self):
        setting = NotificationBackendSetting.objects.create(
            backend_name='matrix', 
            is_active=True, 
            config={'server_url': 'https://matrix.example.com'}
        )
        url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="config"', msg_prefix="Non-email change view should contain raw config textarea")
        self.assertContains(response, 'https://matrix.example.com', msg_prefix="Non-email change view should show existing config data")
        self.assertNotContains(response, 'name="recipient_list"', msg_prefix="Non-email change view should not contain email form fields")

    def test_notificationbackendsetting_change_view_email_shows_custom_form(self):
        initial_email_config = {
            'recipient_list': 'admin@example.com,staff@example.com',
            'from_email': 'system@example.org',
            'host': 'smtp.example.org',
            'port': 587,
            'username': 'emailuser',
            'password': 'securepassword123',
            'use_tls': True,
            'use_ssl': False
        }
        setting = NotificationBackendSetting.objects.create(
            backend_name='email', 
            is_active=True, 
            config=initial_email_config
        )
        url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Raw config textarea should NOT be directly visible (it's replaced by the form fields)
        # Depending on Django admin internals, it might be a hidden field if still part of the underlying ModelForm.
        # A more reliable check is that the custom form fields ARE present.
        # self.assertNotContains(response, '<textarea name="config"') # This might be too strict

        for field_name in EmailBackendConfigForm.base_fields.keys():
            self.assertContains(response, f'name="{field_name}"', msg_prefix=f"Email change view should contain field {field_name}")

        self.assertContains(response, initial_email_config['recipient_list'])
        self.assertContains(response, initial_email_config['host'])
        self.assertContains(response, str(initial_email_config['port']))
        self.assertContains(response, initial_email_config['username'])
        # Password should not be displayed directly, but its input field should be there
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, initial_email_config['password'], msg_prefix="Password should not be rendered in plain text")

        if initial_email_config['use_tls']:
            self.assertContains(response, 'name="use_tls" checked')
        else:
            self.assertContains(response, 'name="use_tls" ') # Check it exists, but not checked
            self.assertNotContains(response, 'name="use_tls" checked')
        
        if initial_email_config['use_ssl']: # Which is false in this test case
            self.assertContains(response, 'name="use_ssl" checked')
        else:
            self.assertContains(response, 'name="use_ssl" ')
            self.assertNotContains(response, 'name="use_ssl" checked')


    def test_notificationbackendsetting_change_view_email_submit_custom_form(self):
        initial_password = "old_secure_password"
        setting = NotificationBackendSetting.objects.create(
            backend_name='email', 
            is_active=True, 
            config={'host': 'old.host.com', 'port': 123, 'password': initial_password}
        )
        change_url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[setting.id])
        
        # 1. Test updating with new data, including a new password
        new_data = {
            'backend_name': 'email', # This field is usually readonly or not part of this form
            'is_active': 'on',
            'recipient_list': 'new_admin@example.com',
            'from_email': 'new_system@example.org',
            'host': 'new.smtp.example.org',
            'port': '588', # Django forms handle string conversion for IntegerField
            'username': 'new_emailuser',
            'password': 'new_password123',
            'use_tls': 'on', # Checkbox data
            'use_ssl': ''    # Checkbox data (not checked)
        }
        response = self.client.post(change_url, data=new_data)
        self.assertEqual(response.status_code, 302) # Successful save redirects
        
        setting.refresh_from_db()
        self.assertTrue(setting.is_active)
        self.assertEqual(setting.config['recipient_list'], new_data['recipient_list'])
        self.assertEqual(setting.config['host'], new_data['host'])
        self.assertEqual(setting.config['port'], 588) # Ensure conversion to int
        self.assertEqual(setting.config['password'], new_data['password'])
        self.assertTrue(setting.config['use_tls'])
        self.assertFalse(setting.config['use_ssl'])

        # 2. Test submitting empty password - should retain old password
        update_no_new_password = new_data.copy()
        update_no_new_password['password'] = '' # Empty password field
        update_no_new_password['host'] = 'another.host.com'

        response = self.client.post(change_url, data=update_no_new_password)
        self.assertEqual(response.status_code, 302)
        setting.refresh_from_db()
        self.assertEqual(setting.config['host'], 'another.host.com')
        self.assertEqual(setting.config['password'], new_data['password'], "Password should be retained if new one is empty")

        # 3. Test submitting empty password when no old password existed
        setting.config = {'host': 'host.without.password.com', 'port': 123} # Remove password from config
        setting.save()
        
        update_empty_password_no_old = new_data.copy()
        update_empty_password_no_old['password'] = ''
        update_empty_password_no_old['host'] = 'final.host.com'

        response = self.client.post(change_url, data=update_empty_password_no_old)
        self.assertEqual(response.status_code, 302)
        setting.refresh_from_db()
        self.assertEqual(setting.config['host'], 'final.host.com')
        self.assertNotIn('password', setting.config, "Password should not be in config if submitted empty and no old one existed")


    def test_save_new_email_backend_two_step_process(self):
        add_url = reverse('admin:tournament_creator_notificationbackendsetting_add')
        
        # Step 1: Add view - POST initial data (raw config)
        initial_add_data = {
            'backend_name': 'email',
            'is_active': 'on',
            'config': json.dumps({'info': 'initial setup, to be replaced'}) 
        }
        response = self.client.post(add_url, data=initial_add_data, follow=False) # Don't follow redirect yet
        
        # Check if a new setting was created
        self.assertEqual(NotificationBackendSetting.objects.count(), 1)
        new_setting = NotificationBackendSetting.objects.first()
        self.assertEqual(new_setting.backend_name, 'email')
        self.assertEqual(new_setting.config.get('info'), 'initial setup, to be replaced')
        
        # Admin redirects to change view after add. Assert this.
        self.assertEqual(response.status_code, 302)
        change_url = response['Location'] # Get the redirect URL (change view)
        expected_change_url = reverse('admin:tournament_creator_notificationbackendsetting_change', args=[new_setting.id])
        self.assertTrue(change_url.endswith(expected_change_url)) #endswith because of host/port

        # Step 2: Change view - GET and verify custom form, then POST updated email config
        response_change_view_get = self.client.get(change_url)
        self.assertEqual(response_change_view_get.status_code, 200)
        for field_name in EmailBackendConfigForm.base_fields.keys():
            self.assertContains(response_change_view_get, f'name="{field_name}"', 
                                msg_prefix=f"Change view for new email backend should show field {field_name}")
        self.assertContains(response_change_view_get, 'initial setup, to be replaced', 
                            msg_prefix="Initial config (if any) should be reflected if form fields match")

        # Now POST detailed email configuration using the custom form
        detailed_email_data = {
            'backend_name': 'email', # Usually readonly on change view
            'is_active': 'on',
            'recipient_list': 'final_admin@example.com',
            'from_email': 'final_system@example.org',
            'host': 'final.smtp.example.org',
            'port': '589',
            'username': 'final_emailuser',
            'password': 'final_password123',
            'use_tls': '',    # Uncheck TLS
            'use_ssl': 'on'   # Check SSL
        }
        response_post_change = self.client.post(change_url, data=detailed_email_data)
        self.assertEqual(response_post_change.status_code, 302) # Successful save

        new_setting.refresh_from_db()
        self.assertEqual(new_setting.config['host'], detailed_email_data['host'])
        self.assertEqual(new_setting.config['port'], 589)
        self.assertEqual(new_setting.config['password'], detailed_email_data['password'])
        self.assertFalse(new_setting.config['use_tls'])
        self.assertTrue(new_setting.config['use_ssl'])
        self.assertNotIn('info', new_setting.config, "Initial raw config should be overwritten by form data")

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
