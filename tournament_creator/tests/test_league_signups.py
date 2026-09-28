"""Tests for sign-up leagues: time slots, players' availability and automatic scheduling."""
from datetime import time, timedelta

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from ..forms import parse_slot_times
from ..models import LeagueAvailability, LeagueSlot, MatchScore, TournamentChart, TournamentSignup, User
from .test_tournament_signups import SignupTestBase


class ParseSlotTimesTests(SimpleTestCase):
    def test_formats(self):
        self.assertEqual(parse_slot_times('18:00, 19.30 20;7'),
                         [time(7), time(18), time(19, 30), time(20)])

    def test_rejects_non_times(self):
        for text in ('25:00', '18:75', 'evening', '', ' , '):
            with self.assertRaises(ValueError):
                parse_slot_times(text)


class LeagueTestBase(SignupTestBase):
    def league(self, category='PAIRS', days=3, hours=(18, 19, 20), **fields):
        fields.setdefault('signup_min', 3 if category == 'PAIRS' else 5)
        tournament = self.signup_tournament(category, format_type='LEAGUE', **fields)
        for week in range(days):
            for hour in hours:
                LeagueSlot.objects.create(tournament=tournament, date=self.start + timedelta(weeks=week),
                                          start_time=time(hour))
        return tournament

    def enter_pairs(self, tournament, count):
        return [TournamentSignup.objects.create(tournament=tournament, player=self.players[2 * i],
                                                partner=self.players[2 * i + 1])
                for i in range(count)]

    def pick(self, signup, player, slots):
        for slot in slots:
            LeagueAvailability.objects.create(signup=signup, player=player, slot=slot)
        signup.mark_times_saved(player)

    def everyone_everywhere(self, tournament):
        slots = list(tournament.league_slots.all())
        for signup in tournament.signups.all():
            for player in signup.players():
                self.pick(signup, player, slots)

    def assert_schedule_respects_availability(self, tournament):
        slot_at = {(s.date, s.start_time): s.id for s in tournament.league_slots.all()}
        picks = set(LeagueAvailability.objects.values_list('player_id', 'slot_id'))
        for matchup in tournament.matchups.exclude(match_date=None):
            slot_id = slot_at[(matchup.match_date, matchup.match_time)]
            for player in (matchup.get_team1_player1(), matchup.get_team1_player2(),
                           matchup.get_team2_player1(), matchup.get_team2_player2()):
                self.assertIn((player.id, slot_id), picks)
            self.assertLessEqual(matchup.court_number, tournament.league_courts)

    def close(self, tournament):
        self.client.login(username='creator', password='test123')
        return self.client.post(reverse('close_signup', args=[tournament.id]))


class LeagueCreationTests(LeagueTestBase):
    def test_creates_slots_and_rules(self):
        day1, day2 = self.start, self.start + timedelta(weeks=1)
        response = self.create('PAIRS', format_type='LEAGUE', slot_date=[day1.isoformat(), day2.isoformat(), ''],
                               slot_times=['18:00, 19:00', '17.30', ''], league_courts=1,
                               league_max_matches_per_day=2, league_avoid_parallel='on')
        tournament = TournamentChart.objects.get(name='Signup Cup')
        self.assertRedirects(response, reverse('tournament_signup', args=[tournament.id]),
                             fetch_redirect_response=False)
        self.assertTrue(tournament.is_signup_league)
        self.assertEqual([(s.date, s.start_time) for s in tournament.league_slots.all()],
                         [(day1, time(18)), (day1, time(19)), (day2, time(17, 30))])
        self.assertEqual(tournament.league_courts, 1)
        self.assertEqual(tournament.league_max_matches_per_day, 2)
        self.assertFalse(tournament.league_back_to_back)  # checkbox left unticked
        self.assertTrue(tournament.league_avoid_parallel)

    def test_create_page_offers_slots(self):
        self.client.login(username='creator', password='test123')
        response = self.client.get(reverse('tournament_create'), {
            'tournament_category': 'PAIRS', 'uses_signup': 'true', 'format_type': 'LEAGUE'})
        self.assertContains(response, 'id="league-settings"')
        self.assertContains(response, 'name="slot_times"')
        self.assertContains(response, 'name="league_avoid_parallel"')

    def test_league_needs_slots(self):
        response = self.create('PAIRS', format_type='LEAGUE', slot_date=[''], slot_times=[''])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add at least one day')
        self.assertFalse(TournamentChart.objects.filter(name='Signup Cup').exists())

    def test_bad_times_are_reported(self):
        response = self.create('PAIRS', format_type='LEAGUE', slot_date=[self.start.isoformat()],
                               slot_times=['after work'])
        self.assertContains(response, 'isn&#x27;t a time')
        self.assertFalse(TournamentChart.objects.filter(name='Signup Cup').exists())

    def test_standard_signup_ignores_slots(self):
        self.create('PAIRS', slot_date=[self.start.isoformat()], slot_times=['18:00'])
        tournament = TournamentChart.objects.get(name='Signup Cup')
        self.assertFalse(tournament.is_signup_league)
        self.assertFalse(tournament.league_slots.exists())


class LeagueTimesTests(LeagueTestBase):
    def setUp(self):
        super().setUp()
        self.tournament = self.league()
        self.slots = list(self.tournament.league_slots.all())
        # The logged-in player (players[0]) with players[1] as partner
        self.signup = TournamentSignup.objects.create(
            tournament=self.tournament, player=self.players[0], partner=self.players[1])
        self.url = reverse('league_times', args=[self.tournament.id])

    def test_player_saves_own_times(self):
        self.client.login(username='player', password='test123')
        response = self.client.post(self.url, {'slots': [self.slots[0].id, self.slots[2].id]})
        self.assertRedirects(response, reverse('tournament_signup', args=[self.tournament.id]),
                             fetch_redirect_response=False)
        self.assertEqual(set(LeagueAvailability.objects.filter(player=self.players[0])
                             .values_list('slot_id', flat=True)), {self.slots[0].id, self.slots[2].id})
        self.signup.refresh_from_db()
        self.assertIsNotNone(self.signup.player_times_saved_at)
        self.assertIsNone(self.signup.partner_times_saved_at)
        # Saving again replaces the picks
        self.client.post(self.url, {'slots': [self.slots[1].id]})
        self.assertEqual(list(LeagueAvailability.objects.filter(player=self.players[0])
                              .values_list('slot_id', flat=True)), [self.slots[1].id])

    def test_saving_no_slots_counts_as_answered(self):
        self.client.login(username='player', password='test123')
        self.client.post(self.url, {})
        self.signup.refresh_from_db()
        self.assertIsNotNone(self.signup.player_times_saved_at)

    def test_partner_picks_are_shown(self):
        self.pick(self.signup, self.players[1], [self.slots[1]])
        self.client.login(username='player', password='test123')
        response = self.client.get(self.url)
        self.assertContains(response, 'slot-chip partner-can', count=1)
        self.assertContains(response, 'Same as')

    def test_partner_answers_separately(self):
        partner_user = User.objects.create_user(username='partner', password='test123', role=User.Role.PLAYER)
        self.players[1].user = partner_user
        self.players[1].save()
        self.client.login(username='partner', password='test123')
        self.client.post(self.url, {'slots': [self.slots[0].id]})
        self.signup.refresh_from_db()
        self.assertIsNotNone(self.signup.partner_times_saved_at)
        self.assertIsNone(self.signup.player_times_saved_at)
        self.assertTrue(LeagueAvailability.objects.filter(player=self.players[1], slot=self.slots[0]).exists())

    def test_director_picks_for_a_player(self):
        self.client.login(username='creator', password='test123')
        response = self.client.post(self.url, {'player': self.players[1].id, 'slots': [self.slots[0].id]})
        self.assertRedirects(response, reverse('league_slots', args=[self.tournament.id]),
                             fetch_redirect_response=False)
        self.assertTrue(LeagueAvailability.objects.filter(player=self.players[1]).exists())

    def test_players_cant_pick_for_others(self):
        self.client.login(username='player', password='test123')
        self.client.post(self.url, {'player': self.players[1].id, 'slots': [self.slots[0].id]})
        self.assertFalse(LeagueAvailability.objects.filter(player=self.players[1]).exists())
        self.assertTrue(LeagueAvailability.objects.filter(player=self.players[0]).exists())

    def test_not_signed_up(self):
        self.signup.delete()
        self.client.login(username='player', password='test123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('tournament_signup', args=[self.tournament.id]),
                             fetch_redirect_response=False)

    def test_withdrawing_removes_picks(self):
        self.pick(self.signup, self.players[0], self.slots)
        self.signup.delete()
        self.assertFalse(LeagueAvailability.objects.exists())

    def test_signup_page_shows_who_has_answered(self):
        self.pick(self.signup, self.players[0], self.slots[:2])
        self.client.login(username='creator', password='test123')
        response = self.client.get(reverse('tournament_signup', args=[self.tournament.id]))
        self.assertContains(response, "1 player haven")  # the partner
        self.assertContains(response, 'Time slots &amp; scheduling rules')


class LeagueSlotsPageTests(LeagueTestBase):
    def setUp(self):
        super().setUp()
        self.tournament = self.league(days=1, hours=(18,))
        self.url = reverse('league_slots', args=[self.tournament.id])
        self.client.login(username='creator', password='test123')

    def test_page_shows_slots_and_who_can_play(self):
        signup = self.enter_pairs(self.tournament, 1)[0]
        slot = self.tournament.league_slots.get()
        self.pick(signup, self.players[0], [slot])
        response = self.client.get(self.url)
        self.assertContains(response, 'title="P1 Test"')
        self.assertContains(response, '1 player haven')
        self.assertContains(response, f'?player={self.players[1].id}')

    def test_add_day_skips_existing_times(self):
        self.client.post(self.url, {'action': 'add_day', 'day-date': self.start.isoformat(),
                                    'day-times': '18:00 19:00'})
        self.assertEqual([s.start_time for s in self.tournament.league_slots.all()], [time(18), time(19)])

    def test_delete_slot(self):
        slot = self.tournament.league_slots.get()
        self.client.post(self.url, {'action': 'delete_slot', 'slot': slot.id})
        self.assertFalse(self.tournament.league_slots.exists())

    def test_save_rules(self):
        self.client.post(self.url, {'action': 'rules', 'rules-league_courts': 3,
                                    'rules-league_max_matches_per_day': '', 'rules-league_back_to_back': 'on'})
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.league_courts, 3)
        self.assertIsNone(self.tournament.league_max_matches_per_day)
        self.assertTrue(self.tournament.league_back_to_back)
        self.assertFalse(self.tournament.league_avoid_parallel)

    def test_directors_only(self):
        self.client.login(username='player', password='test123')
        response = self.client.post(self.url, {'action': 'delete_slot',
                                               'slot': self.tournament.league_slots.get().id})
        self.assertRedirects(response, reverse('tournament_signup', args=[self.tournament.id]),
                             fetch_redirect_response=False)
        self.assertTrue(self.tournament.league_slots.exists())


class LeagueSchedulingTests(LeagueTestBase):
    def test_closing_schedules_matches(self):
        tournament = self.league()
        self.enter_pairs(tournament, 4)
        self.everyone_everywhere(tournament)
        response = self.close(tournament)
        self.assertRedirects(response, reverse('tournament_detail', args=[tournament.id]),
                             fetch_redirect_response=False)
        matchups = list(tournament.matchups.all())
        self.assertEqual(len(matchups), 6)
        self.assertTrue(all(m.match_date and m.match_time for m in matchups))
        self.assert_schedule_respects_availability(tournament)
        # The last round, with seeds 1 v 2, is played last
        last = max(matchups, key=lambda m: (m.match_date, m.match_time))
        self.assertEqual(last.round_number, 3)

    def test_moc_league(self):
        tournament = self.league('MOC', days=4)
        for player in self.players[:5]:
            TournamentSignup.objects.create(tournament=tournament, player=player)
        self.everyone_everywhere(tournament)
        self.close(tournament)
        self.assertTrue(tournament.matchups.exists())
        self.assertFalse(tournament.matchups.filter(match_date=None).exists())
        self.assert_schedule_respects_availability(tournament)

    def test_partner_availability_is_intersected(self):
        tournament = self.league(days=1, hours=(18, 19))
        signups = self.enter_pairs(tournament, 2)  # one match
        tournament.signup_min = 2
        tournament.save()
        slot18, slot19 = tournament.league_slots.all()
        self.pick(signups[0], self.players[0], [slot18, slot19])
        self.pick(signups[0], self.players[1], [slot19])
        self.pick(signups[1], self.players[2], [slot18, slot19])
        self.pick(signups[1], self.players[3], [slot18, slot19])
        self.close(tournament)
        matchup = tournament.matchups.get()
        self.assertEqual(matchup.match_time, time(19))

    def test_unplaceable_matches_stay_undated_and_are_listed(self):
        tournament = self.league()
        signups = self.enter_pairs(tournament, 4)
        self.everyone_everywhere(tournament)
        LeagueAvailability.objects.filter(player=self.players[7]).delete()  # pair 4 can't play
        self.close(tournament)
        undated = tournament.matchups.filter(match_date=None)
        self.assertEqual(undated.count(), 3)
        self.assertTrue(all(signups[3].player_id in (m.pair1.player1_id, m.pair2.player1_id) for m in undated))
        response = self.client.get(reverse('tournament_detail', args=[tournament.id]))
        self.assertContains(response, 'Not scheduled yet')
        self.assertContains(response, '3 matches have no date yet')

    def test_schedule_unplaced_keeps_dated_matches(self):
        tournament = self.league()
        self.enter_pairs(tournament, 4)
        self.everyone_everywhere(tournament)
        LeagueAvailability.objects.filter(player=self.players[7]).delete()
        self.close(tournament)
        before = {m.id: (m.match_date, m.match_time) for m in tournament.matchups.exclude(match_date=None)}
        # Pair 4 answers late
        signup = TournamentSignup.objects.get(tournament=tournament, player=self.players[6])
        self.pick(signup, self.players[7], tournament.league_slots.all())
        self.client.post(reverse('league_schedule', args=[tournament.id]), {'mode': 'unplaced'})
        self.assertFalse(tournament.matchups.filter(match_date=None).exists())
        after = {m.id: (m.match_date, m.match_time) for m in tournament.matchups.filter(id__in=before)}
        self.assertEqual(before, after)
        self.assert_schedule_respects_availability(tournament)

    def test_reschedule_all_keeps_played_matches(self):
        tournament = self.league(league_courts=1)
        self.enter_pairs(tournament, 4)
        self.everyone_everywhere(tournament)
        self.close(tournament)
        played = tournament.matchups.order_by('match_date', 'match_time').first()
        MatchScore.objects.create(matchup=played, set_number=1, team1_score=15, team2_score=10)
        kept = (played.match_date, played.match_time)
        # Nobody can make the played match's slot any more; the rest must move
        LeagueAvailability.objects.filter(slot__date=kept[0], slot__start_time=kept[1]).delete()
        self.client.post(reverse('league_schedule', args=[tournament.id]), {'mode': 'all'})
        played.refresh_from_db()
        self.assertEqual((played.match_date, played.match_time), kept)
        self.assertFalse(tournament.matchups.filter(match_date=kept[0], match_time=kept[1])
                         .exclude(id=played.id).exists())
        self.assertFalse(tournament.matchups.filter(match_date=None).exists())

    def test_next_phase_is_scheduled_around_the_first(self):
        tournament = self.league(signup_pairs_format='RR_PLAYOFFS', days=4)
        self.enter_pairs(tournament, 4)
        self.everyone_everywhere(tournament)
        self.close(tournament)
        first_phase = {m.id: (m.match_date, m.match_time) for m in tournament.matchups.all()}
        from ..simulation import record_result
        for matchup in tournament.matchups.all():
            record_result(tournament, matchup, [21], [15], self.creator)
        self.client.post(reverse('generate_next_stage', args=[tournament.id]))
        semis = tournament.matchups.exclude(id__in=first_phase)
        self.assertEqual(semis.count(), 2)
        self.assertFalse(semis.filter(match_date=None).exists())
        self.assertEqual({m.id: (m.match_date, m.match_time) for m in tournament.matchups.filter(id__in=first_phase)},
                         first_phase)

    def test_avoid_parallel_uses_one_court(self):
        tournament = self.league(league_courts=2, league_avoid_parallel=True, days=3, hours=(18, 19))
        self.enter_pairs(tournament, 4)  # 6 matches, 6 slots
        self.everyone_everywhere(tournament)
        self.close(tournament)
        self.assertEqual(set(tournament.matchups.values_list('court_number', flat=True)), {1})

    def test_schedule_is_directors_only(self):
        tournament = self.league()
        self.enter_pairs(tournament, 4)
        self.close(tournament)
        tournament.matchups.update(match_date=None, match_time=None)
        self.client.login(username='player', password='test123')
        self.client.post(reverse('league_schedule', args=[tournament.id]), {'mode': 'all'})
        self.assertEqual(tournament.matchups.filter(match_date=None).count(), 6)


class LeagueSimulationTests(LeagueTestBase):
    def test_sandbox_simulation_fills_signups_and_times(self):
        tournament = self.league(is_sandbox=True, signup_max=6)
        self.client.login(username='player', password='test123')
        self.client.post(reverse('simulate_league_signups', args=[tournament.id]))
        signups = list(tournament.signups.all())
        self.assertEqual(len(signups), 6)
        self.assertTrue(all(s.partner_id for s in signups))
        self.assertTrue(all(s.player_times_saved_at and s.partner_times_saved_at for s in signups))
        self.assertTrue(LeagueAvailability.objects.filter(slot__tournament=tournament).exists())

    def test_only_sandboxes(self):
        tournament = self.league()
        self.client.login(username='creator', password='test123')
        self.client.post(reverse('simulate_league_signups', args=[tournament.id]))
        self.assertFalse(tournament.signups.exists())

    def test_simulated_league_can_be_scheduled(self):
        tournament = self.league(is_sandbox=True, signup_max=6, days=6)
        from ..simulation import simulate_availability, simulate_signups
        import random
        simulate_signups(tournament, self.creator, rng=random.Random(3))
        simulate_availability(tournament, rng=random.Random(3))
        self.close(tournament)
        self.assertEqual(tournament.matchups.count(), 15)
        self.assert_schedule_respects_availability(tournament)
