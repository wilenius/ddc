"""Tests for sign-up tournaments: creation, signing up, withdrawing and closing."""
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from ..models import Pair, Player, TournamentChart, TournamentSignup, User


class SignupTestBase(TestCase):
    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username='creator', password='test123', role=User.Role.TOURNAMENT_CREATOR)
        self.players = [
            Player.objects.create(first_name=f'P{i}', last_name='Test', ranking=i, ranking_points=100 - i)
            for i in range(1, 21)
        ]
        self.player_user = User.objects.create_user(
            username='player', password='test123', role=User.Role.PLAYER)
        self.players[0].user = self.player_user
        self.players[0].save()
        # Establishes Helsinki/Finland as a known location
        TournamentChart.objects.create(
            name='Existing', place='Helsinki', country='Finland',
            date=timezone.now().date(), number_of_rounds=7, number_of_courts=2,
        )
        self.start = timezone.localdate() + timedelta(days=10)

    def create(self, category='MOC', **overrides):
        data = {
            'name': 'Signup Cup', 'place': 'Helsinki', 'country': 'Finland',
            'date': self.start, 'tournament_category': category,
            'format_type': 'STANDARD', 'name_display_format': 'FIRST',
            'uses_signup': 'on',
        }
        if category == 'PAIRS':
            data.update({'pairs_format': 'ROUND_ROBIN', 'round_robin_points': 21,
                         'round_robin_cap': 23, 'round_robin_sets': 1})
        data.update(overrides)
        self.client.login(username='creator', password='test123')
        response = self.client.post(reverse('tournament_create'), data)
        self.client.logout()
        return response

    def signup_tournament(self, category='MOC', **fields):
        defaults = dict(
            name='Signup Cup', place='Helsinki', country='Finland', date=self.start,
            number_of_rounds=0, number_of_courts=0, uses_signup=True, signup_category=category,
            signup_deadline=timezone.now() + timedelta(days=5), signup_min=4 if category == 'PAIRS' else 5,
            signup_max=10 if category == 'PAIRS' else 16, created_by=self.creator,
        )
        defaults.update(fields)
        return TournamentChart.objects.create(**defaults)


class SignupCreationTests(SignupTestBase):
    def test_creates_tournament_without_entrants_and_with_defaults(self):
        response = self.create()
        tournament = TournamentChart.objects.get(name='Signup Cup')
        self.assertRedirects(response, reverse('tournament_signup', args=[tournament.id]),
                             fetch_redirect_response=False)
        self.assertTrue(tournament.awaiting_signups)
        self.assertEqual(tournament.signup_category, 'MOC')
        self.assertEqual((tournament.signup_min, tournament.signup_max), (5, 16))
        deadline = timezone.localtime(tournament.signup_deadline)
        self.assertEqual(deadline.date(), self.start - timedelta(days=2))
        self.assertEqual((deadline.hour, deadline.minute), (23, 59))
        self.assertFalse(tournament.matchups.exists())

    def test_create_page_offers_the_signup_sheet(self):
        self.client.login(username='creator', password='test123')
        for category in ('MOC', 'PAIRS'):
            response = self.client.get(reverse('tournament_create'),
                                       {'tournament_category': category, 'uses_signup': 'true'})
            self.assertContains(response, 'id="signup-settings"')
            self.assertContains(response, 'name="signup_deadline"')

    def test_pairs_limits_follow_the_playing_format(self):
        self.create('PAIRS')
        tournament = TournamentChart.objects.get(name='Signup Cup')
        self.assertEqual((tournament.signup_min, tournament.signup_max), (4, 10))
        self.assertEqual(tournament.signup_pairs_format, 'ROUND_ROBIN')
        self.assertIn('round_robin', tournament.match_rules)

    def test_maximum_above_the_largest_format_is_rejected(self):
        response = self.create(signup_max=17)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'signup_max', 'The maximum must be between 5 and 16 players.')

    def test_deadline_after_the_start_is_rejected(self):
        late = (self.start + timedelta(days=1)).strftime('%Y-%m-%dT12:00')
        response = self.create(signup_deadline=late)
        self.assertFormError(response.context['form'], 'signup_deadline',
                             "The sign-up deadline can't be after the tournament starts.")

    def test_detail_page_redirects_to_signup_until_closed(self):
        tournament = self.signup_tournament()
        self.client.login(username='player', password='test123')
        response = self.client.get(reverse('tournament_detail', args=[tournament.id]))
        self.assertRedirects(response, reverse('tournament_signup', args=[tournament.id]))


class SigningUpTests(SignupTestBase):
    def test_player_signs_up_and_withdraws(self):
        tournament = self.signup_tournament()
        self.client.login(username='player', password='test123')
        url = reverse('tournament_signup', args=[tournament.id])
        self.client.post(url, {'action': 'signup'})
        signup = TournamentSignup.objects.get(tournament=tournament)
        self.assertEqual(signup.player, self.players[0])
        self.assertEqual(signup.signed_up_by, self.player_user)

        self.client.post(url, {'action': 'withdraw', 'signup': signup.id})
        self.assertFalse(TournamentSignup.objects.filter(tournament=tournament).exists())

    def test_doubles_signup_needs_a_partner_who_is_not_entered(self):
        tournament = self.signup_tournament('PAIRS')
        TournamentSignup.objects.create(tournament=tournament, player=self.players[2], partner=self.players[3])
        self.client.login(username='player', password='test123')
        url = reverse('tournament_signup', args=[tournament.id])

        response = self.client.post(url, {'action': 'signup'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tournament.signups.count(), 1)

        response = self.client.post(url, {'action': 'signup', 'me-partner': self.players[3].id})
        self.assertEqual(response.status_code, 200)  # partner already entered
        self.assertEqual(tournament.signups.count(), 1)

        self.client.post(url, {'action': 'signup', 'me-partner': self.players[1].id})
        signup = tournament.signups.get(player=self.players[0])
        self.assertEqual(signup.partner, self.players[1])

    def test_no_signup_after_the_deadline(self):
        tournament = self.signup_tournament(signup_deadline=timezone.now() - timedelta(minutes=1))
        self.client.login(username='player', password='test123')
        self.client.post(reverse('tournament_signup', args=[tournament.id]), {'action': 'signup'})
        self.assertFalse(tournament.signups.exists())

    def test_no_signup_when_full(self):
        tournament = self.signup_tournament(signup_max=5)
        for player in self.players[1:6]:
            TournamentSignup.objects.create(tournament=tournament, player=player)
        self.client.login(username='player', password='test123')
        self.client.post(reverse('tournament_signup', args=[tournament.id]), {'action': 'signup'})
        self.assertEqual(tournament.signups.count(), 5)

    def test_spectators_cannot_sign_up(self):
        tournament = self.signup_tournament()
        spectator = User.objects.create_user(username='spec', password='test123', role=User.Role.SPECTATOR)
        self.players[5].user = spectator
        self.players[5].save()
        self.client.login(username='spec', password='test123')
        self.client.post(reverse('tournament_signup', args=[tournament.id]), {'action': 'signup'})
        self.assertFalse(tournament.signups.exists())

    def test_players_cannot_remove_other_entries_but_directors_can(self):
        tournament = self.signup_tournament()
        other = TournamentSignup.objects.create(tournament=tournament, player=self.players[4])
        url = reverse('tournament_signup', args=[tournament.id])
        self.client.login(username='player', password='test123')
        self.client.post(url, {'action': 'withdraw', 'signup': other.id})
        self.assertTrue(tournament.signups.filter(id=other.id).exists())

        self.client.login(username='creator', password='test123')
        self.client.post(url, {'action': 'withdraw', 'signup': other.id})
        self.assertFalse(tournament.signups.filter(id=other.id).exists())

    def test_director_adds_entries_after_the_deadline(self):
        tournament = self.signup_tournament('PAIRS', signup_deadline=timezone.now() - timedelta(minutes=1))
        self.client.login(username='creator', password='test123')
        self.client.post(reverse('tournament_signup', args=[tournament.id]), {
            'action': 'add', 'add-player': self.players[6].id, 'add-partner': self.players[7].id,
        })
        signup = tournament.signups.get()
        self.assertEqual((signup.player, signup.partner), (self.players[6], self.players[7]))


class CloseSignupTests(SignupTestBase):
    def test_closing_moc_creates_the_schedule(self):
        tournament = self.signup_tournament()
        for player in self.players[:6]:
            TournamentSignup.objects.create(tournament=tournament, player=player)
        self.client.login(username='creator', password='test123')
        response = self.client.post(reverse('close_signup', args=[tournament.id]))
        self.assertRedirects(response, reverse('tournament_detail', args=[tournament.id]))
        tournament.refresh_from_db()
        self.assertFalse(tournament.awaiting_signups)
        self.assertEqual(tournament.archetype.name, '6-player Monarch of the Court')
        self.assertEqual(tournament.players.count(), 6)
        self.assertTrue(tournament.matchups.exists())

    def test_closing_pairs_makes_pairs_from_the_entries(self):
        tournament = self.signup_tournament('PAIRS', match_rules={
            'round_robin': {'points_to': 21, 'cap': 23, 'best_of': 1}})
        for i in range(0, 8, 2):
            TournamentSignup.objects.create(tournament=tournament, player=self.players[i], partner=self.players[i + 1])
        self.client.login(username='creator', password='test123')
        self.client.post(reverse('close_signup', args=[tournament.id]))
        tournament.refresh_from_db()
        self.assertEqual(tournament.archetype.name, '4 pairs doubles tournament')
        pairs = {(p.player1_id, p.player2_id) for p in tournament.pairs.all()}
        self.assertEqual(pairs, {(self.players[i].id, self.players[i + 1].id) for i in range(0, 8, 2)})
        self.assertEqual(Pair.objects.get(player1=self.players[0]).seed, 1)

    def test_closing_below_the_minimum_is_refused(self):
        tournament = self.signup_tournament()
        for player in self.players[:4]:
            TournamentSignup.objects.create(tournament=tournament, player=player)
        self.client.login(username='creator', password='test123')
        self.client.post(reverse('close_signup', args=[tournament.id]))
        tournament.refresh_from_db()
        self.assertTrue(tournament.awaiting_signups)
        self.assertFalse(tournament.matchups.exists())

    def test_only_directors_can_close(self):
        tournament = self.signup_tournament()
        for player in self.players[:6]:
            TournamentSignup.objects.create(tournament=tournament, player=player)
        self.client.login(username='player', password='test123')
        self.client.post(reverse('close_signup', args=[tournament.id]))
        tournament.refresh_from_db()
        self.assertTrue(tournament.awaiting_signups)
