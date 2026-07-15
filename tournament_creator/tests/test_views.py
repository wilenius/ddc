from django.test import TestCase, SimpleTestCase, Client
from django.urls import reverse
from datetime import timedelta
from unittest.mock import patch
from ..models import Player, TournamentChart, TournamentArchetype, User, Matchup, MatchScore
from ..models.notifications import NotificationBackendSetting # Added
from ..models.logging import MatchResultLog
from ..models.scoring import PlayerScore
from ..forms import TournamentCreationForm # Added
from ..views.tournament_views import _score_rule_warnings
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
            'format_type': 'STANDARD',
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
        """Match results are editable by participants and admins on current
        tournaments, and locked for non-admins once a tournament is past."""
        # Link the player user to a player competing in this tournament.
        self.players[0].user = self.player_user
        self.players[0].save()

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

        # A logged-in user who isn't competing (and isn't admin) is denied.
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

        # A player competing in the tournament can record.
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Admin can always record.
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Once the tournament is in the past, non-admins are locked out...
        self.tournament.date = timezone.now().date() - timedelta(days=2)
        self.tournament.save()
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

        # ...but admins retain access to fix past results.
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
            'format_type': 'STANDARD',
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


class TournamentListTabsTests(TestCase):
    """Tests for upcoming/past/archived tabs on the tournament list."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_test', password='test123', role='ADMIN')
        self.spectator_user = User.objects.create_user(
            username='spectator_test', password='test123', role='SPECTATOR')

        today = timezone.now().date()

        self.upcoming = TournamentChart.objects.create(
            name='Upcoming Cup', date=today + timedelta(days=10),
            number_of_rounds=7, number_of_courts=2)
        # Ongoing (started, ends in the future) counts as upcoming/current.
        self.ongoing = TournamentChart.objects.create(
            name='Ongoing Cup', date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            number_of_rounds=7, number_of_courts=2)
        self.past = TournamentChart.objects.create(
            name='Past Cup', date=today - timedelta(days=30),
            number_of_rounds=7, number_of_courts=2)
        self.archived = TournamentChart.objects.create(
            name='Iloranta Open', date=today - timedelta(days=60),
            number_of_rounds=7, number_of_courts=2, archived=True)

    def test_tabs_categorize_tournaments(self):
        self.client.login(username='spectator_test', password='test123')
        response = self.client.get(reverse('tournament_list'))
        self.assertEqual(response.status_code, 200)

        upcoming_names = {t.name for t in response.context['upcoming_tournaments']}
        past_names = {t.name for t in response.context['past_tournaments']}

        self.assertEqual(upcoming_names, {'Upcoming Cup', 'Ongoing Cup'})
        self.assertEqual(past_names, {'Past Cup'})

    def test_archived_hidden_from_non_admin(self):
        self.client.login(username='spectator_test', password='test123')
        response = self.client.get(reverse('tournament_list'))

        self.assertEqual(response.context['archived_tournaments'], [])
        # Archived tournament must not leak into the other tabs either.
        all_shown = (response.context['upcoming_tournaments']
                     + response.context['past_tournaments'])
        self.assertNotIn(self.archived, all_shown)
        self.assertNotContains(response, 'Iloranta Open')

    def test_archived_visible_to_admin(self):
        self.client.login(username='admin_test', password='test123')
        response = self.client.get(reverse('tournament_list'))

        archived_names = {t.name for t in response.context['archived_tournaments']}
        self.assertEqual(archived_names, {'Iloranta Open'})
        self.assertContains(response, 'Iloranta Open')
        # Archived stays out of upcoming/past even for admins.
        past_names = {t.name for t in response.context['past_tournaments']}
        self.assertNotIn('Iloranta Open', past_names)

class ScoreRuleWarningsTests(SimpleTestCase):
    """Unit tests for the warn-and-confirm score validation logic."""

    BO1_21 = {'points_to': 21, 'cap': 23, 'best_of': 1}
    BO3_15 = {'points_to': 15, 'cap': 18, 'best_of': 3}
    SETS_FREE = {'points_to': 21, 'cap': 23, 'best_of': None}

    def assertConforms(self, rules, team1, team2):
        self.assertEqual(_score_rule_warnings(rules, team1, team2), [])

    def assertFlagged(self, rules, team1, team2, expected_warnings=1):
        warnings = _score_rule_warnings(rules, team1, team2)
        self.assertEqual(len(warnings), expected_warnings,
                         f"{team1} vs {team2}: {warnings}")

    def test_conforming_single_games(self):
        self.assertConforms(self.BO1_21, [21], [15])   # straight win
        self.assertConforms(self.BO1_21, [21], [19])   # minimal win-by-2
        self.assertConforms(self.BO1_21, [22], [20])   # deuce
        self.assertConforms(self.BO1_21, [23], [21])   # win-by-2 exactly at the cap
        self.assertConforms(self.BO1_21, [23], [22])   # cap win by 1
        self.assertConforms(self.BO1_21, [15], [21])   # team order doesn't matter

    def test_flagged_single_games(self):
        self.assertFlagged(self.BO1_21, [21], [20])    # win by 1
        self.assertFlagged(self.BO1_21, [24], [20])    # over the cap
        self.assertFlagged(self.BO1_21, [15], [10])    # underplayed
        self.assertFlagged(self.BO1_21, [21], [21])    # tie
        self.assertFlagged(self.BO1_21, [22], [19])    # unreachable past deuce
        self.assertFlagged(self.BO1_21, [23], [19])    # unreachable cap score

    def test_set_count_single_game(self):
        # Right per-set scores, but a single-game match with two sets entered.
        self.assertFlagged(self.BO1_21, [21, 21], [15, 15])

    def test_best_of_three(self):
        self.assertConforms(self.BO3_15, [15, 15], [10, 12])        # 2-0
        self.assertConforms(self.BO3_15, [15, 10, 15], [8, 15, 13])  # 2-1
        self.assertFlagged(self.BO3_15, [15], [10])                 # incomplete: 1-0
        self.assertFlagged(self.BO3_15, [15, 10], [10, 15])         # incomplete: 1-1
        self.assertFlagged(self.BO3_15, [15, 15, 15], [10, 10, 10])  # dead third set

    def test_free_set_count_validates_sets_only(self):
        # best_of None (sandbox): any number of sets, each set still checked.
        self.assertConforms(self.SETS_FREE, [21, 21, 21], [15, 15, 15])
        self.assertFlagged(self.SETS_FREE, [21, 5], [15, 3])


class SandboxTournamentTests(TestCase):
    """Sandbox (practice) tournaments: recording open to any logged-in user,
    warn-and-confirm score checks, no notifications, and a reset endpoint."""

    def setUp(self):
        self.client = Client()
        # A spectator who is NOT competing — normally the most restricted role.
        self.spectator_user = User.objects.create_user(
            username='sandbox_spectator', password='test123', role='SPECTATOR')
        self.players = [
            Player.objects.create(first_name=f'S{i}', last_name='Box', ranking=i + 1)
            for i in range(4)
        ]
        # Dated in the past on purpose: sandboxes must never lock.
        self.tournament = TournamentChart.objects.create(
            name='Recording Practice',
            date=timezone.now().date() - timedelta(days=30),
            number_of_rounds=3, number_of_courts=1,
            is_sandbox=True, notify_by_signal=True, notify_by_email=True,
        )
        self.tournament.players.set(self.players)
        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament, round_number=1, court_number=1,
            pair1_player1=self.players[0], pair1_player2=self.players[1],
            pair2_player1=self.players[2], pair2_player2=self.players[3])
        self.record_url = reverse('record_match_result', kwargs={
            'tournament_id': self.tournament.id, 'matchup_id': self.matchup.id})
        self.reset_url = reverse('reset_sandbox_scores', kwargs={
            'tournament_id': self.tournament.id})
        self.client.login(username='sandbox_spectator', password='test123')

    def record(self, team1='[21]', team2='[15]', **extra):
        return self.client.post(self.record_url, {
            'team1_scores': team1, 'team2_scores': team2, **extra})

    def test_any_logged_in_user_can_record_even_when_past(self):
        response = self.record()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(self.matchup.scores.count(), 1)

    def test_nonconforming_score_prompts_confirmation(self):
        # Sandboxes rehearse the Euros pool-phase format (to 21, cap 23).
        response = self.record(team1='[15]', team2='[10]')
        data = response.json()
        self.assertEqual(data['status'], 'needs_confirmation')
        self.assertTrue(data['warnings'])
        self.assertEqual(self.matchup.scores.count(), 0)

        response = self.record(team1='[15]', team2='[10]', confirmed='1')
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(self.matchup.scores.count(), 1)

    def test_sandbox_never_notifies(self):
        with patch('tournament_creator.views.tournament_views.send_email_notification') as email_mock, \
             patch('tournament_creator.views.tournament_views.send_signal_notification') as signal_mock:
            response = self.record()
        self.assertEqual(response.json()['status'], 'success')
        email_mock.assert_not_called()
        signal_mock.assert_not_called()

    def test_reset_clears_results(self):
        self.record()
        self.assertTrue(PlayerScore.objects.filter(tournament=self.tournament).exists())
        self.assertTrue(MatchResultLog.objects.filter(matchup=self.matchup).exists())

        response = self.client.post(self.reset_url)
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(self.matchup.scores.count(), 0)
        self.assertFalse(MatchResultLog.objects.filter(matchup=self.matchup).exists())
        self.assertFalse(PlayerScore.objects.filter(tournament=self.tournament).exists())

    def test_reset_refused_for_regular_tournament(self):
        self.tournament.is_sandbox = False
        self.tournament.save()
        # Have something recorded (as admin, since the sandbox rules no longer apply).
        MatchScore.objects.create(matchup=self.matchup, set_number=1,
                                  team1_score=21, team2_score=15)
        response = self.client.post(self.reset_url)
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(self.matchup.scores.count(), 1)

    def test_detail_page_shows_banner_and_reset_button(self):
        response = self.client.get(reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Practice tournament')
        self.assertContains(response, 'Reset all results')
        # A sandbox never shows the past-tournament lock notice.
        self.assertNotContains(response, 'results can no longer be edited')

    def test_regular_formats_have_no_score_rules(self):
        self.assertIsNone(TournamentArchetype().get_score_rules(self.matchup))
