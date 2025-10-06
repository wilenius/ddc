from django.test import TestCase, Client
from django.urls import reverse
from ..models import Player, TournamentChart, TournamentArchetype, User, Matchup
from ..models.notifications import NotificationBackendSetting # Added
from ..forms import TournamentCreationForm # Added
from django.utils import timezone

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='test123',
            role='ADMIN'
        )
        self.player_user = User.objects.create_user(
            username='player_test',
            password='test123',
            role='PLAYER'
        )
        self.spectator_user = User.objects.create_user(
            username='spectator_test',
            password='test123',
            role='SPECTATOR'
        )

        # Create test data
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            self.players.append(player)

        self.archetype = TournamentArchetype.objects.create(
            name="5-player MOC Test", # Changed for MOC 5 player logic
            description='Test MOC tournament type for 5 players',
            tournament_category='MOC' # Added category
        )
        self.moc_players = self.players[:5] # Select 5 players for MOC

        self.tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)

    def test_tournament_list_view(self):
        """Test tournament list view access"""
        url = reverse('tournament_list')
        
        # Unauthenticated user should be redirected to login
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Authenticated users should have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Tournament')

    def test_tournament_create_permissions(self):
        """Test tournament creation permissions"""
        url = reverse('tournament_create')
        data = {
            'name': 'New Tournament',
            'date': timezone.now().date(),
            'tournament_category': 'MOC',
            'number_of_stages': 1,
            'name_display_format': 'FIRST',
            'players': [player.id for player in self.players[:5]]  # 5 players for MOC
        }

        # Spectator should not have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)

        # Player should have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_record_match_result_permissions(self):
        """Test match result recording permissions"""
        # Create a matchup
        matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[1],
            pair2_player1=self.players[2],
            pair2_player2=self.players[3]
        )

        url = reverse('record_match_result', kwargs={
            'tournament_id': self.tournament.id,
            'matchup_id': matchup.id
        })

        data = {
            'team1_scores': '[15]',
            'team2_scores': '[11]',
            'winning_team': '1'
        }

        # Any logged-in user can record scores (including spectators)
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Player should have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_tournament_delete_permissions(self):
        """Test tournament deletion permissions"""
        url = reverse('tournament_delete', kwargs={'pk': self.tournament.pk})
        
        # Unauthenticated user should be redirected to login
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        # Spectator should not have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        
        # Player should not have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        
        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Verify tournament was deleted
        self.assertFalse(TournamentChart.objects.filter(pk=self.tournament.pk).exists())

    # Tests for TournamentCreateView GET
    def test_get_tournament_create_view_no_notification_settings(self):
        self.client.login(username='player_test', password='test123')
        response = self.client.get(reverse('tournament_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], TournamentCreationForm)
        self.assertIn('notify_by_email', response.context['form'].fields)
        self.assertIn('notify_by_signal', response.context['form'].fields)
        self.assertIn('notify_by_matrix', response.context['form'].fields)
        
        self.assertIn('notification_backend_settings', response.context)
        # Assuming default_if_none:False in template, or view initializes all to False if not found
        self.assertFalse(response.context['notification_backend_settings'].get('email'))
        self.assertFalse(response.context['notification_backend_settings'].get('signal'))
        self.assertFalse(response.context['notification_backend_settings'].get('matrix'))

    def test_get_tournament_create_view_with_notification_settings(self):
        self.client.login(username='player_test', password='test123')
        NotificationBackendSetting.objects.create(backend_name='email', is_active=True, config={'host': 'test.com'})
        NotificationBackendSetting.objects.create(backend_name='signal', is_active=False, config={'url': 'http://signal.test'})
        # Matrix backend not created, should default to False

        response = self.client.get(reverse('tournament_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], TournamentCreationForm)
        self.assertIn('notification_backend_settings', response.context)
        self.assertTrue(response.context['notification_backend_settings']['email'])
        self.assertFalse(response.context['notification_backend_settings']['signal'])
        self.assertFalse(response.context['notification_backend_settings'].get('matrix')) # Should be False as it's not active

    # Test for TournamentCreateView POST
    def test_post_tournament_create_view_success_with_notifications(self):
        self.client.login(username='player_test', password='test123')
        initial_tournament_count = TournamentChart.objects.count()

        post_data = {
            'name': 'Notify Test Tournament',
            'date': timezone.now().date().isoformat(),
            'tournament_category': 'MOC',
            'number_of_stages': 1,
            'name_display_format': 'FIRST',
            'players': [p.id for p in self.moc_players], # For MOC player selection
            'notify_by_email': 'on', # Checkbox value for True
            # notify_by_signal is not sent, so it should be False
            'notify_by_matrix': 'on', # Checkbox value for True
        }
        
        # Ensure the selected archetype is MOC for the view's logic
        self.assertEqual(self.archetype.tournament_category, 'MOC')

        response = self.client.post(reverse('tournament_create'), data=post_data)
        
        # Check for redirect, url depends on success_url of CreateView, or if it's overridden
        # Typically to tournament_detail or tournament_list
        self.assertEqual(response.status_code, 302, f"POST failed with errors: {response.context.get('form').errors if response.context else 'No form in context'}") 
        
        self.assertEqual(TournamentChart.objects.count(), initial_tournament_count + 1)
        new_tournament = TournamentChart.objects.latest('id')
        self.assertEqual(new_tournament.name, 'Notify Test Tournament')
        self.assertTrue(new_tournament.notify_by_email)
        self.assertFalse(new_tournament.notify_by_signal) # Was not in POST data
        self.assertTrue(new_tournament.notify_by_matrix)

    def test_tournament_creation_preserves_name_date_after_archetype_selection(self):
        self.client.login(username='player_test', password='test123')

        # Step 1: Initial GET (optional, but good for completeness)
        response_initial = self.client.get(reverse('tournament_create'))
        self.assertEqual(response_initial.status_code, 200)

        # Step 2: Simulate selecting a tournament category with initial name and date
        test_name = "My Preserved Tournament"
        test_date_str = "2024-08-15" # Use ISO format string
        test_category = "MOC"

        category_selection_url = f"{reverse('tournament_create')}?tournament_category={test_category}&name={test_name}&date={test_date_str}"
        response = self.client.get(category_selection_url)
        self.assertEqual(response.status_code, 200)

        # Assertions for form initial values
        form = response.context.get('form')
        self.assertIsNotNone(form, "Form not found in context")
        self.assertIsInstance(form, TournamentCreationForm)
        self.assertEqual(form.initial.get('name'), test_name)
        self.assertEqual(form.initial.get('date'), test_date_str)

        # Assertions for selected category in context
        selected_category_in_context = response.context.get('selected_category')
        self.assertEqual(selected_category_in_context, test_category)

        # Assertions for HTML content (as a cross-check)
        # Ensure the name and date input fields are correctly populated.
        # The exact HTML structure depends on how {{ form.name }} and {{ form.date }} render.
        # Django's default widgets for CharField and DateField will have `value="..."`.
        self.assertContains(response, f'value="{test_name}"')
        self.assertContains(response, f'value="{test_date_str}"')

        # Check if the correct category option is selected in the dropdown
        self.assertContains(response, f'<option value="{test_category}" selected')