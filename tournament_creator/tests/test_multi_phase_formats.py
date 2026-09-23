from django.test import TestCase, Client
from django.urls import reverse

from ..forms import TournamentCreationForm
from ..models import (Player, Pair, TournamentChart, TournamentArchetype, MatchScore, User)
from ..models.tournament_types import (
    DoubleRoundRobinFormat, RoundRobinPlayoffsFormat, get_implementation,
)


class MultiPhaseTestBase(TestCase):
    """A tournament of ``num_pairs`` pairs in ``impl_class``'s format, stage 1 generated."""
    impl_class = None
    num_pairs = 6

    def setUp(self):
        self.impl = self.impl_class()
        self.pairs = []
        for i in range(1, self.num_pairs + 1):
            player1 = Player.objects.create(
                first_name=f'P{i}a', last_name='Test', ranking=i * 2 - 1, ranking_points=1000 - i)
            player2 = Player.objects.create(
                first_name=f'P{i}b', last_name='Test', ranking=i * 2, ranking_points=1000 - i)
            self.pairs.append(Pair.objects.create(player1=player1, player2=player2, seed=i, entry_order=i))

        self.tournament = TournamentChart.objects.create(
            name='Multi-phase Test',
            date='2026-10-01',
            number_of_rounds=self.impl.calculate_rounds(self.num_pairs),
            number_of_courts=self.impl.calculate_courts(self.num_pairs),
            number_of_stages=len(self.impl.STAGES),
            archetype=TournamentArchetype.objects.get(name=self.impl.ARCHETYPE_NAME),
        )
        self.tournament.pairs.set(self.pairs)
        self.stages = self.impl.create_stages(self.tournament)
        self.impl.generate_matchups(self.tournament, self.pairs, stage=self.stages[0])

    def seed(self, seed):
        return next(p for p in self.pairs if p.seed == seed)

    def record_win(self, matchup, winner_pair, winner_score=21, loser_score=15):
        if matchup.pair1_id == winner_pair.id:
            team1_score, team2_score = winner_score, loser_score
        else:
            team1_score, team2_score = loser_score, winner_score
        matchup.scores.all().delete()
        MatchScore.objects.create(matchup=matchup, set_number=1,
                                  team1_score=team1_score, team2_score=team2_score)
        self.impl.maybe_generate_placement_matches(self.tournament, matchup)

    def play_stage(self, stage, strength):
        """Score every matchup; the pair ranked first in ``strength`` (seed order) wins."""
        for matchup in stage.matchups.all():
            winner = min((matchup.pair1, matchup.pair2), key=lambda p: strength.index(p.seed))
            self.record_win(matchup, winner)


class RoundRobinPlayoffsSixPairsTest(MultiPhaseTestBase):
    impl_class = RoundRobinPlayoffsFormat
    num_pairs = 6

    def test_registered_implementation(self):
        self.assertIsInstance(get_implementation(self.tournament.archetype), RoundRobinPlayoffsFormat)

    def test_structure(self):
        self.assertEqual([s.name for s in self.stages], ['Round robin', 'Playoffs'])
        self.assertEqual(self.tournament.number_of_rounds, 5 + 2)
        self.assertEqual(self.tournament.number_of_courts, 3)
        stage1 = self.stages[0]
        self.assertEqual(stage1.pools.count(), 1)
        self.assertEqual(stage1.matchups.count(), 15)  # everyone plays everyone once
        self.assertFalse(self.stages[1].matchups.exists())

    def test_advance_blocked_until_round_robin_complete(self):
        with self.assertRaises(ValueError):
            self.impl.advance_to_next_stage(self.tournament)

    def test_top_four_play_semis(self):
        # Seed 6 wins everything, then seeds 1, 2, 3...
        self.play_stage(self.stages[0], strength=[6, 1, 2, 3, 4, 5])
        stage2 = self.impl.advance_to_next_stage(self.tournament)
        self.assertEqual(stage2, self.stages[1])
        group = stage2.pools.get()
        self.assertEqual(group.name, 'Top 4')
        semis = list(stage2.matchups.order_by('court_number'))
        self.assertEqual(len(semis), 2)
        self.assertEqual([(m.pair1.seed, m.pair2.seed, m.court_number, m.label) for m in semis],
                         [(6, 3, 1, 'Semifinal'), (1, 2, 2, 'Semifinal')])
        with self.assertRaises(ValueError):
            self.impl.advance_to_next_stage(self.tournament)

    def test_final_bronze_and_final_standings(self):
        self.play_stage(self.stages[0], strength=[1, 2, 3, 4, 5, 6])
        self.impl.advance_to_next_stage(self.tournament)
        self.assertIsNone(self.impl.get_final_standings(self.tournament))
        # Upsets in both semis: 4 beats 1, 3 beats 2
        semi1, semi2 = self.stages[1].matchups.order_by('court_number')
        self.record_win(semi1, self.seed(4))
        self.assertEqual(self.stages[1].matchups.count(), 2)  # waits for the other semi
        self.record_win(semi2, self.seed(3))
        final, bronze = self.stages[1].matchups.filter(round_number=2).order_by('court_number')
        self.assertEqual((final.label, {final.pair1.seed, final.pair2.seed}), ('Final', {3, 4}))
        self.assertEqual((bronze.label, {bronze.pair1.seed, bronze.pair2.seed}), ('Bronze match', {1, 2}))
        self.assertEqual(final.court_number, 1)

        self.record_win(final, self.seed(3))
        self.assertIsNone(self.impl.get_final_standings(self.tournament))
        self.record_win(bronze, self.seed(2))
        standings = self.impl.get_final_standings(self.tournament)
        self.assertEqual([(e['position'], e['pair'].seed) for e in standings],
                         [(1, 3), (2, 4), (3, 2), (4, 1), (5, 5), (6, 6)])

    def test_tie_for_third_decided_by_head_to_head(self):
        # 1 and 2 beat everyone below them; 3, 4 and 5 beat 6 and each other in
        # a circle (3>5, 4>3, 5>4), so all three end on 2 wins. 5's big win over
        # 4 gives it the best head-to-head PD: 5 (+10), 3 (0), 4 (-10).
        results = {
            (1, 2): 1, (1, 3): 1, (1, 4): 1, (1, 5): 1, (1, 6): 1,
            (2, 3): 2, (2, 4): 2, (2, 5): 2, (2, 6): 2,
            (3, 4): 4, (3, 5): 3, (3, 6): 3,
            (4, 5): 5, (4, 6): 4, (5, 6): 5,
        }
        for matchup in self.stages[0].matchups.all():
            seeds = tuple(sorted((matchup.pair1.seed, matchup.pair2.seed)))
            loser_score = 5 if seeds == (4, 5) else 15
            self.record_win(matchup, self.seed(results[seeds]), loser_score=loser_score)
        standings = self.impl.get_pool_standings(self.stages[0].pools.get())
        self.assertEqual([e['pair'].seed for e in standings], [1, 2, 5, 3, 4, 6])

        self.impl.advance_to_next_stage(self.tournament)
        semis = self.stages[1].matchups.order_by('court_number')
        self.assertEqual([(m.pair1.seed, m.pair2.seed) for m in semis], [(1, 3), (2, 5)])


class RoundRobinPlayoffsSevenPairsTest(MultiPhaseTestBase):
    impl_class = RoundRobinPlayoffsFormat
    num_pairs = 7

    def test_seven_pairs(self):
        self.assertEqual(self.tournament.number_of_rounds, 7 + 2)
        self.assertEqual(self.tournament.number_of_courts, 3)
        self.assertEqual(self.stages[0].matchups.count(), 21)
        self.play_stage(self.stages[0], strength=[1, 2, 3, 4, 5, 6, 7])
        self.impl.advance_to_next_stage(self.tournament)
        for semi in self.stages[1].matchups.all():
            self.record_win(semi, min((semi.pair1, semi.pair2), key=lambda p: p.seed))
        for match in self.stages[1].matchups.filter(round_number=2):
            self.record_win(match, min((match.pair1, match.pair2), key=lambda p: p.seed))
        standings = self.impl.get_final_standings(self.tournament)
        self.assertEqual([e['pair'].seed for e in standings], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([e['position'] for e in standings], list(range(1, 8)))


class DoubleRoundRobinTest(MultiPhaseTestBase):
    impl_class = DoubleRoundRobinFormat
    num_pairs = 7

    def test_structure(self):
        self.assertEqual([s.name for s in self.stages], ['Round robin 1', 'Round robin 2'])
        self.assertEqual(self.tournament.number_of_rounds, 14)
        self.assertEqual(self.stages[0].matchups.count(), 21)

    def test_second_round_robin_reseeded(self):
        # Seed 5 wins round robin 1, seed 3 is second
        strength = [5, 3, 1, 2, 4, 6, 7]
        self.play_stage(self.stages[0], strength=strength)
        stage2 = self.impl.advance_to_next_stage(self.tournament)
        pool = stage2.pools.get()
        self.assertEqual([pp.pair.seed for pp in pool.poolpair_set.order_by('position')], strength)
        self.assertEqual(stage2.matchups.count(), 21)

        # The top two meet in the last round
        last_round = max(m.round_number for m in stage2.matchups.all())
        last = stage2.matchups.filter(round_number=last_round)
        self.assertIn({5, 3}, [{m.pair1.seed, m.pair2.seed} for m in last])
        # The leader plays every match on court 1
        for matchup in stage2.matchups.all():
            if self.seed(5).id in (matchup.pair1_id, matchup.pair2_id):
                self.assertEqual(matchup.court_number, 1)

    def test_standings_count_both_round_robins(self):
        self.play_stage(self.stages[0], strength=[1, 2, 3, 4, 5, 6, 7])
        self.impl.advance_to_next_stage(self.tournament)
        self.assertIsNone(self.impl.get_final_standings(self.tournament))
        # Round robin 2 goes to seed 2, who beats seed 1 by more than it lost to
        # it in round 1: both end on 11 wins, and head-to-head PD puts 2 first.
        for matchup in self.stages[1].matchups.all():
            winner = min((matchup.pair1, matchup.pair2),
                         key=lambda p: [2, 1, 3, 4, 5, 6, 7].index(p.seed))
            self.record_win(matchup, winner, loser_score=5 if winner.seed == 2 else 15)
        standings = self.impl.get_pool_standings(self.stages[1].pools.get())
        self.assertEqual([(e['pair'].seed, e['wins'], e['matches_played']) for e in standings[:2]],
                         [(2, 11, 12), (1, 11, 12)])
        final = self.impl.get_final_standings(self.tournament)
        self.assertEqual([e['pair'].seed for e in final], [2, 1, 3, 4, 5, 6, 7])


class MatchRulesTest(MultiPhaseTestBase):
    impl_class = RoundRobinPlayoffsFormat
    num_pairs = 4

    def test_defaults_without_stored_rules(self):
        self.assertEqual(self.impl.get_score_rules(self.stages[0].matchups.first()),
                         {'points_to': 21, 'cap': 23, 'best_of': 1})

    def test_rules_per_match_type(self):
        self.tournament.match_rules = {
            'round_robin': {'points_to': 15, 'cap': 18, 'best_of': 1},
            'semifinal': {'points_to': 21, 'cap': 23, 'best_of': 3},
            'bronze': {'points_to': 11, 'cap': 13, 'best_of': 1},
            'final': {'points_to': 21, 'cap': 25, 'best_of': 5},
        }
        self.tournament.save()
        self.assertEqual(self.impl.get_score_rules(self.stages[0].matchups.first()),
                         {'points_to': 15, 'cap': 18, 'best_of': 1})
        self.play_stage(self.stages[0], strength=[1, 2, 3, 4])
        self.impl.advance_to_next_stage(self.tournament)
        for semi in self.stages[1].matchups.all():
            self.assertEqual(self.impl.get_score_rules(semi)['best_of'], 3)
            self.record_win(semi, min((semi.pair1, semi.pair2), key=lambda p: p.seed))
        final, bronze = self.stages[1].matchups.filter(round_number=2).order_by('court_number')
        self.assertEqual(self.impl.get_score_rules(final), {'points_to': 21, 'cap': 25, 'best_of': 5})
        self.assertEqual(self.impl.get_score_rules(bronze), {'points_to': 11, 'cap': 13, 'best_of': 1})


class MultiPhaseCreationViewTest(TestCase):
    """Creating doubles tournaments with a chosen playing format and match rules."""

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='creator_test', password='test123', role='TC')
        self.client.login(username='creator_test', password='test123')
        self.players = [
            Player.objects.create(first_name=f'F{i}', last_name=f'L{i}', ranking=i,
                                  ranking_points=1000 - i)
            for i in range(1, 21)
        ]

    def create(self, num_pairs, **extra):
        data = {
            'name': 'SM 2026',
            'place': 'Helsinki',
            'country': 'Finland',
            'confirm_new_location': TournamentCreationForm.location_token('Helsinki', 'Finland'),
            'date': '2026-10-01',
            'tournament_category': 'PAIRS',
            'format_type': 'STANDARD',
            'name_display_format': 'FIRST',
            'players': [p.id for p in self.players[:num_pairs * 2]],
        }
        data.update(extra)
        return self.client.post(reverse('tournament_create'), data=data)

    def test_create_round_robin_with_playoffs(self):
        response = self.create(
            6, pairs_format='RR_PLAYOFFS',
            round_robin_points=21, round_robin_cap=23, round_robin_sets=1,
            semifinal_points=15, semifinal_cap=18, semifinal_sets=3,
            bronze_points=21, bronze_cap=23, bronze_sets=1,
            final_points=21, final_cap='', final_sets=3,  # blank cap → suggested
        )
        self.assertEqual(response.status_code, 302)
        tournament = TournamentChart.objects.latest('id')
        self.assertEqual(tournament.archetype.name, 'Round robin + top-4 playoffs')
        self.assertEqual(tournament.number_of_stages, 2)
        self.assertEqual(tournament.stages.get(stage_number=1).matchups.count(), 15)
        self.assertEqual(tournament.match_rules, {
            'round_robin': {'points_to': 21, 'cap': 23, 'best_of': 1},
            'semifinal': {'points_to': 15, 'cap': 18, 'best_of': 3},
            'bronze': {'points_to': 21, 'cap': 23, 'best_of': 1},
            'final': {'points_to': 21, 'cap': 23, 'best_of': 3},
        })

    def test_only_rules_of_played_match_types_are_stored(self):
        response = self.create(
            5, pairs_format='DOUBLE_RR',
            round_robin_points=15, round_robin_cap='', round_robin_sets=1,
            semifinal_points=15, semifinal_cap=18, semifinal_sets=3,
        )
        self.assertEqual(response.status_code, 302)
        tournament = TournamentChart.objects.latest('id')
        self.assertEqual(tournament.archetype.name, 'Double round robin, reseeded')
        self.assertEqual(tournament.match_rules,
                         {'round_robin': {'points_to': 15, 'cap': 18, 'best_of': 1}})

    def test_plain_round_robin_validates_against_its_rules(self):
        response = self.create(6, pairs_format='ROUND_ROBIN',
                               round_robin_points=11, round_robin_cap=13, round_robin_sets=3)
        self.assertEqual(response.status_code, 302)
        tournament = TournamentChart.objects.latest('id')
        self.assertEqual(tournament.archetype.name, '6 pairs doubles tournament')
        impl = get_implementation(tournament.archetype)
        self.assertEqual(impl.get_score_rules(tournament.matchups.first()),
                         {'points_to': 11, 'cap': 13, 'best_of': 3})

    def test_blank_format_picks_plain_round_robin(self):
        self.assertEqual(self.create(6).status_code, 302)
        tournament = TournamentChart.objects.latest('id')
        self.assertEqual(tournament.archetype.name, '6 pairs doubles tournament')
        self.assertEqual(tournament.match_rules, {})

    def test_format_that_doesnt_fit_pair_count_is_rejected(self):
        response = self.create(3, pairs_format='RR_PLAYOFFS')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TournamentChart.objects.exists())
        self.assertContains(response, 'needs 4–10 pairs')

    def test_cap_below_points_is_rejected(self):
        response = self.create(6, pairs_format='ROUND_ROBIN',
                               round_robin_points=21, round_robin_cap=15, round_robin_sets=1)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TournamentChart.objects.exists())
        self.assertContains(response, "the cap can&#x27;t be below the points")

    def test_create_page_lists_playing_formats(self):
        response = self.client.get(reverse('tournament_create') + '?tournament_category=PAIRS')
        self.assertContains(response, 'Round robin + top-4 playoffs')
        self.assertContains(response, 'data-rule-row="semifinal"')

    def test_detail_page_through_the_playoffs(self):
        self.create(4, pairs_format='RR_PLAYOFFS')
        tournament = TournamentChart.objects.latest('id')
        detail = reverse('tournament_detail', args=[tournament.id])
        self.assertContains(self.client.get(detail), 'All pairs')
        for matchup in tournament.matchups.all():
            MatchScore.objects.create(matchup=matchup, set_number=1, team1_score=21, team2_score=15)
        self.assertContains(self.client.get(detail), 'Generate Playoffs')
        self.client.post(reverse('generate_next_stage', args=[tournament.id]))
        response = self.client.get(detail)
        self.assertContains(response, 'Top 4')
        self.assertContains(response, 'Semifinal')


class SimulateSandboxScoresTest(TestCase):
    """The practice tournament's "Simulate results" button."""

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='creator_test', password='test123', role='TC')
        self.client.login(username='creator_test', password='test123')
        players = [Player.objects.create(first_name=f'F{i}', last_name=f'L{i}', ranking=i,
                                         ranking_points=1000 - 10 * i)
                   for i in range(1, 13)]
        self.client.post(reverse('tournament_create'), data={
            'name': 'Practice', 'place': 'Helsinki', 'country': 'Finland',
            'confirm_new_location': TournamentCreationForm.location_token('Helsinki', 'Finland'),
            'date': '2026-10-01', 'tournament_category': 'PAIRS', 'format_type': 'STANDARD',
            'name_display_format': 'FIRST', 'is_sandbox': 'on',
            'players': [p.id for p in players], 'pairs_format': 'RR_PLAYOFFS',
            'round_robin_points': 11, 'round_robin_cap': 13, 'round_robin_sets': 1,
            'semifinal_points': 15, 'semifinal_cap': 18, 'semifinal_sets': 3,
            'bronze_points': 21, 'bronze_cap': 23, 'bronze_sets': 1,
            'final_points': 21, 'final_cap': 23, 'final_sets': 3,
        })
        self.tournament = TournamentChart.objects.latest('id')
        self.url = reverse('simulate_sandbox_scores', args=[self.tournament.id])

    def test_simulates_by_each_matchs_rules(self):
        self.client.post(self.url)
        round_robin = self.tournament.stages.get(stage_number=1)
        self.assertFalse(round_robin.matchups.filter(scores__isnull=True).exists())
        for matchup in round_robin.matchups.all():
            (score,) = matchup.scores.all()  # one game
            self.assertLessEqual(max(score.team1_score, score.team2_score), 13)
            self.assertGreaterEqual(max(score.team1_score, score.team2_score), 11)

        # Playoffs: semis, then the final and bronze match created along the way
        self.client.post(reverse('generate_next_stage', args=[self.tournament.id]))
        self.client.post(self.url)
        playoffs = self.tournament.stages.get(stage_number=2)
        self.assertEqual(playoffs.matchups.count(), 4)
        self.assertFalse(playoffs.matchups.filter(scores__isnull=True).exists())
        for semi in playoffs.matchups.filter(round_number=1):
            self.assertIn(semi.scores.count(), (2, 3))  # best of 3
        impl = get_implementation(self.tournament.archetype)
        self.assertIsNotNone(impl.get_final_standings(self.tournament))

    def test_only_for_practice_tournaments(self):
        self.tournament.is_sandbox = False
        self.tournament.save()
        self.client.post(self.url)
        self.assertFalse(MatchScore.objects.exists())

    def test_button_shown_on_practice_tournament(self):
        response = self.client.get(reverse('tournament_detail', args=[self.tournament.id]))
        self.assertContains(response, 'Simulate results')

    def test_management_command_still_simulates(self):
        from io import StringIO
        from django.core.management import call_command
        call_command('simulate_scores', self.tournament.id, '--points', '21', '--sets', '1',
                     stdout=StringIO())
        stage1 = self.tournament.stages.get(stage_number=1)
        self.assertFalse(stage1.matchups.filter(scores__isnull=True).exists())
