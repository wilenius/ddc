from django.test import TestCase, Client
from django.urls import reverse
from ..models import (Player, Pair, TournamentChart, TournamentArchetype, Matchup, MatchScore,
                      Pool, PoolPair, User, ManualPoolTiebreakResolution)
from ..models.tournament_types import EurosFormat, get_implementation


class EurosFormatTestBase(TestCase):
    """Shared setup: a 20-pair tournament with phase 1 generated."""

    def setUp(self):
        self.impl = EurosFormat()
        self.pairs = []
        for i in range(1, 21):
            player1 = Player.objects.create(
                first_name=f'P{i}a', last_name='Test', ranking=i * 2 - 1, ranking_points=1000 - i)
            player2 = Player.objects.create(
                first_name=f'P{i}b', last_name='Test', ranking=i * 2, ranking_points=1000 - i)
            pair = Pair.objects.create(player1=player1, player2=player2, seed=i, entry_order=i)
            self.pairs.append(pair)

        self.archetype = TournamentArchetype.objects.get(name="20 pairs euros format")
        self.tournament = TournamentChart.objects.create(
            name='Euros Test',
            date='2026-07-01',
            number_of_rounds=self.impl.calculate_rounds(20),
            number_of_courts=self.impl.calculate_courts(20),
            number_of_stages=3,
            archetype=self.archetype,
        )
        self.tournament.pairs.set(self.pairs)
        self.stages = self.impl.create_stages(self.tournament)
        self.impl.generate_matchups(self.tournament, self.pairs, stage=self.stages[0])

    def pair_by_seed(self, seed):
        return next(p for p in self.pairs if p.seed == seed)

    def record_win(self, matchup, winner_pair, winner_score=11, loser_score=5):
        """Record a one-set result where winner_pair wins."""
        if matchup.pair1_id == winner_pair.id:
            team1_score, team2_score = winner_score, loser_score
        elif matchup.pair2_id == winner_pair.id:
            team1_score, team2_score = loser_score, winner_score
        else:
            raise AssertionError(f"Pair {winner_pair} is not in matchup {matchup}")
        matchup.scores.all().delete()
        MatchScore.objects.create(
            matchup=matchup, set_number=1,
            team1_score=team1_score, team2_score=team2_score)

    def play_stage_lower_seed_wins(self, stage):
        """Score every matchup in a stage with the lower-seeded (stronger) pair winning."""
        for matchup in stage.matchups.all():
            winner = matchup.pair1 if matchup.pair1.seed < matchup.pair2.seed else matchup.pair2
            self.record_win(matchup, winner)

    def pool_seed_sets(self, stage):
        """Returns a list (in pool order) of the sets of pair seeds in each pool."""
        return [
            set(pp.pair.seed for pp in PoolPair.objects.filter(pool=pool))
            for pool in stage.pools.order_by('order')
        ]

    def advance_through_phase2(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        self.impl.advance_to_next_stage(self.tournament)
        self.play_stage_lower_seed_wins(self.stages[1])
        self.impl.advance_to_next_stage(self.tournament)

    def play_finals(self):
        """Play semis (lower seed wins), generate placement matches, play those too."""
        finals = self.stages[2]
        for pool in finals.pools.all():
            semis = list(pool.matchups.filter(round_number=1))
            for semi in semis:
                winner = semi.pair1 if semi.pair1.seed < semi.pair2.seed else semi.pair2
                self.record_win(semi, winner)
                self.impl.maybe_generate_placement_matches(self.tournament, semi)
        for matchup in finals.matchups.filter(round_number=2):
            winner = matchup.pair1 if matchup.pair1.seed < matchup.pair2.seed else matchup.pair2
            self.record_win(matchup, winner)


class EurosPhase1Test(EurosFormatTestBase):

    def test_registered_implementation(self):
        self.assertIsInstance(get_implementation(self.archetype), EurosFormat)

    def test_snake_seeding_pools(self):
        expected = [
            {1, 10, 11, 20},  # Pool A
            {2, 9, 12, 19},   # Pool B
            {3, 8, 13, 18},   # Pool C
            {4, 7, 14, 17},   # Pool D
            {5, 6, 15, 16},   # Pool E
        ]
        self.assertEqual(self.pool_seed_sets(self.stages[0]), expected)
        names = [pool.name for pool in self.stages[0].pools.order_by('order')]
        self.assertEqual(names, ['Pool A', 'Pool B', 'Pool C', 'Pool D', 'Pool E'])

    def test_phase1_matchup_structure(self):
        stage1_matchups = self.stages[0].matchups.all()
        # 5 pools x 6 round robin matches = 30 matchups over 3 rounds
        self.assertEqual(stage1_matchups.count(), 30)
        self.assertEqual(
            sorted(set(stage1_matchups.values_list('round_number', flat=True))), [1, 2, 3])
        # Each pair plays exactly 3 matches, one per round
        for pair in self.pairs:
            count = stage1_matchups.filter(
                pool__isnull=False).filter(
                pair1=pair).count() + stage1_matchups.filter(pair2=pair).count()
            self.assertEqual(count, 3, f"Pair seeded {pair.seed} should have 3 matches")
        # Pools use disjoint courts: pool i on courts 2i+1, 2i+2
        for pool_idx, pool in enumerate(self.stages[0].pools.order_by('order')):
            courts = set(pool.matchups.values_list('court_number', flat=True))
            self.assertEqual(courts, {pool_idx * 2 + 1, pool_idx * 2 + 2})

    def test_all_pool_matchups_are_within_pool(self):
        for pool in self.stages[0].pools.all():
            member_ids = set(PoolPair.objects.filter(pool=pool).values_list('pair_id', flat=True))
            for matchup in pool.matchups.all():
                self.assertIn(matchup.pair1_id, member_ids)
                self.assertIn(matchup.pair2_id, member_ids)


class EurosAdvancementTest(EurosFormatTestBase):

    def test_advance_blocked_when_phase1_incomplete(self):
        with self.assertRaises(ValueError):
            self.impl.advance_to_next_stage(self.tournament)
        # Also blocked when only some matches are scored
        first = self.stages[0].matchups.first()
        self.record_win(first, first.pair1)
        with self.assertRaises(ValueError):
            self.impl.advance_to_next_stage(self.tournament)

    def test_phase2_pools(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        stage = self.impl.advance_to_next_stage(self.tournament)
        self.assertEqual(stage.id, self.stages[1].id)

        # Top 2 of each pool -> A Pool, bottom 2 -> B Pool
        a_seeds, b_seeds = self.pool_seed_sets(self.stages[1])
        self.assertEqual(a_seeds, {1, 2, 3, 4, 5, 6, 7, 8, 9, 10})
        self.assertEqual(b_seeds, {11, 12, 13, 14, 15, 16, 17, 18, 19, 20})

        # Full 10-team round robin in each pool: 45 matches over 9 rounds, 9 per pair
        for pool, court_range in zip(self.stages[1].pools.order_by('order'),
                                     [{1, 2, 3, 4, 5}, {6, 7, 8, 9, 10}]):
            matchups = pool.matchups.all()
            self.assertEqual(matchups.count(), 45)
            self.assertEqual(
                sorted(set(matchups.values_list('round_number', flat=True))), list(range(1, 10)))
            self.assertEqual(set(matchups.values_list('court_number', flat=True)), court_range)
            for pp in PoolPair.objects.filter(pool=pool):
                played = matchups.filter(pair1=pp.pair).count() + matchups.filter(pair2=pp.pair).count()
                self.assertEqual(played, 9)

    def test_former_pool_mates_meet_again_in_phase2(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        self.impl.advance_to_next_stage(self.tournament)
        # Seeds 1 and 10 were both in Pool A and both advance to the A Pool:
        # they must play each other again in phase 2.
        pair1, pair10 = self.pair_by_seed(1), self.pair_by_seed(10)
        rematch = self.stages[1].matchups.filter(pair1=pair1, pair2=pair10).count() + \
            self.stages[1].matchups.filter(pair1=pair10, pair2=pair1).count()
        self.assertEqual(rematch, 1)

    def test_finals_groups_and_semis(self):
        self.advance_through_phase2()
        finals = self.stages[2]

        # Provisional order with lower-seed-wins is just seed order,
        # so groups are 1-4, 5-8, 9-12, 13-16, 17-20
        expected_groups = [set(range(base + 1, base + 5)) for base in range(0, 20, 4)]
        self.assertEqual(self.pool_seed_sets(finals), expected_groups)
        names = [pool.name for pool in finals.pools.order_by('order')]
        self.assertEqual(names, ['Places 1-4', 'Places 5-8', 'Places 9-12', 'Places 13-16', 'Places 17-20'])

        # Each group plays semis 1v4 and 2v3 (by provisional position within the group)
        for base, pool in zip(range(0, 20, 4), finals.pools.order_by('order')):
            semis = pool.matchups.filter(round_number=1)
            self.assertEqual(semis.count(), 2)
            semi_pairings = {frozenset((m.pair1.seed, m.pair2.seed)) for m in semis}
            self.assertEqual(semi_pairings, {
                frozenset((base + 1, base + 4)),
                frozenset((base + 2, base + 3)),
            })

    def test_group_9_to_12_mixes_a_and_b_pool(self):
        """The 2 worst from the A Pool and the 2 best from the B Pool share a finals group."""
        self.advance_through_phase2()
        groups = self.pool_seed_sets(self.stages[2])
        # With lower-seed-wins, A Pool ranks 9-10 are seeds 9, 10 and B Pool ranks 1-2 are seeds 11, 12
        self.assertEqual(groups[2], {9, 10, 11, 12})

    def test_advance_fails_after_all_stages_generated(self):
        self.advance_through_phase2()
        with self.assertRaises(ValueError):
            self.impl.advance_to_next_stage(self.tournament)


class EurosFinalsTest(EurosFormatTestBase):

    def test_placement_matches_generated_after_semis(self):
        self.advance_through_phase2()
        finals = self.stages[2]
        pool = finals.pools.order_by('order').first()  # Places 1-4: seeds 1, 2, 3, 4
        semis = list(pool.matchups.filter(round_number=1).order_by('court_number'))

        # Scoring only one semi must not create placement matches yet
        self.record_win(semis[0], self.pair_by_seed(1))
        self.impl.maybe_generate_placement_matches(self.tournament, semis[0])
        self.assertFalse(pool.matchups.filter(round_number=2).exists())

        # After the second semi, the final (winners) and consolation (losers) appear
        self.record_win(semis[1], self.pair_by_seed(2))
        self.impl.maybe_generate_placement_matches(self.tournament, semis[1])
        placement = list(pool.matchups.filter(round_number=2).order_by('court_number'))
        self.assertEqual(len(placement), 2)
        self.assertEqual({placement[0].pair1.seed, placement[0].pair2.seed}, {1, 2})
        self.assertEqual({placement[1].pair1.seed, placement[1].pair2.seed}, {3, 4})

        # Calling again must not duplicate the placement matches
        self.impl.maybe_generate_placement_matches(self.tournament, semis[1])
        self.assertEqual(pool.matchups.filter(round_number=2).count(), 2)

    def test_final_standings(self):
        self.advance_through_phase2()
        self.assertIsNone(self.impl.get_final_standings(self.tournament))
        self.play_finals()
        standings = self.impl.get_final_standings(self.tournament)
        self.assertIsNotNone(standings)
        self.assertEqual(len(standings), 20)
        # With lower-seed-wins throughout, the final placement is exactly seed order
        for entry in standings:
            self.assertEqual(entry['position'], entry['pair'].seed)

    def test_every_pair_plays_14_matches(self):
        self.advance_through_phase2()
        self.play_finals()
        for pair in self.pairs:
            played = Matchup.objects.filter(tournament_chart=self.tournament).filter(
                pair1=pair).count() + Matchup.objects.filter(
                tournament_chart=self.tournament).filter(pair2=pair).count()
            self.assertEqual(played, 14, f"Pair seeded {pair.seed} should play 14 matches")


class EurosStandingsTest(EurosFormatTestBase):

    def test_pool_standings_simple(self):
        pool_a = self.stages[0].pools.order_by('order').first()
        self.play_stage_lower_seed_wins(self.stages[0])
        standings = self.impl.get_pool_standings(pool_a)
        self.assertEqual([e['pair'].seed for e in standings], [1, 10, 11, 20])
        self.assertEqual([e['wins'] for e in standings], [3, 2, 1, 0])
        self.assertEqual([e['position'] for e in standings], [1, 2, 3, 4])

    def test_pool_standings_circular_tie_broken_by_h2h_point_difference(self):
        """
        Pool A (seeds 1, 10, 11, 20): seed 1 wins everything; the other three beat
        each other in a circle, so head-to-head wins are level (1 each) and the
        head-to-head point difference decides.
        """
        pool_a = self.stages[0].pools.order_by('order').first()
        matchups = {
            frozenset((m.pair1.seed, m.pair2.seed)): m for m in pool_a.matchups.all()
        }
        p1, p10, p11, p20 = (self.pair_by_seed(s) for s in (1, 10, 11, 20))
        self.record_win(matchups[frozenset((1, 10))], p1)
        self.record_win(matchups[frozenset((1, 11))], p1)
        self.record_win(matchups[frozenset((1, 20))], p1)
        self.record_win(matchups[frozenset((10, 11))], p10, winner_score=11, loser_score=1)   # +10
        self.record_win(matchups[frozenset((11, 20))], p11, winner_score=11, loser_score=9)   # +2
        self.record_win(matchups[frozenset((10, 20))], p20, winner_score=11, loser_score=9)   # +2

        standings = self.impl.get_pool_standings(pool_a)
        # H2H PD: seed 10 = +10-2 = +8, seed 20 = +2-2 = 0, seed 11 = -10+2 = -8
        self.assertEqual([e['pair'].seed for e in standings], [1, 10, 20, 11])

    def _make_five_pair_pool(self):
        """
        A synthetic 5-pair pool (seeds 1-5) on stage 1 where seeds 2/3/4 end up
        in a circular tie with level head-to-head wins AND level head-to-head PD,
        so the tie can only be resolved by the later steps:
          - seed 1 beats everyone (margins vs 2/3/4: 2, 6, 10)
          - circle: 2 beats 3, 3 beats 4, 4 beats 2, all by 4 (h2h: 1 win, 0 PD each)
          - seed 5 loses to everyone (margins vs 2/3/4: 1, 3, 13)
        PD vs above (step 5): 2 → -2, 3 → -6, 4 → -10 (order 2, 3, 4)
        Overall PD (step 6):  2 → -1, 3 → -3, 4 → +3 (order 4, 2, 3) — different!
        """
        pool = Pool.objects.create(stage=self.stages[0], name='Test Pool', order=99)
        by_seed = {s: self.pair_by_seed(s) for s in (1, 2, 3, 4, 5)}
        for position, seed in enumerate((1, 2, 3, 4, 5), start=1):
            PoolPair.objects.create(pool=pool, pair=by_seed[seed], position=position)
        matchups = {}
        pairs_list = [by_seed[s] for s in (1, 2, 3, 4, 5)]
        court = 1
        for i, pair1 in enumerate(pairs_list):
            for pair2 in pairs_list[i + 1:]:
                m = Matchup.objects.create(
                    tournament_chart=self.tournament, stage=self.stages[0], pool=pool,
                    pair1=pair1, pair2=pair2, round_number=1, court_number=court)
                matchups[frozenset((pair1.seed, pair2.seed))] = m
                court += 1

        def win(seed_a, seed_b, margin):
            self.record_win(matchups[frozenset((seed_a, seed_b))], by_seed[seed_a],
                            winner_score=15, loser_score=15 - margin)

        win(1, 2, 2)
        win(1, 3, 6)
        win(1, 4, 10)
        win(1, 5, 5)
        win(2, 3, 4)
        win(3, 4, 4)
        win(4, 2, 4)
        win(2, 5, 1)
        win(3, 5, 3)
        win(4, 5, 13)
        return pool

    def test_tie_resolved_by_pd_against_above_teams_not_overall_pd(self):
        """Step 5 (PD vs teams placed above) must be applied before step 6 (overall PD)."""
        pool = self._make_five_pair_pool()
        standings = self.impl.get_pool_standings(pool)
        # Overall PD alone would give 1, 4, 2, 3 — PD vs above (seed 1) gives 1, 2, 3, 4.
        self.assertEqual([e['pair'].seed for e in standings], [1, 2, 3, 4, 5])
        tied = {e['pair'].seed: e for e in standings if e.get('tied')}
        self.assertEqual(set(tied), {2, 3, 4})
        for seed in (2, 3, 4):
            self.assertEqual(tied[seed]['h2h_wins'], 1)
            self.assertEqual(tied[seed]['h2h_losses'], 1)
            self.assertEqual(tied[seed]['h2h_pd'], 0)
            self.assertEqual(tied[seed]['above_wins'], 0)
        self.assertEqual([tied[s]['above_pd'] for s in (2, 3, 4)], [-2, -6, -10])

    def test_manual_resolution_overrides_automatic_order(self):
        """Step 7: a director's manual resolution reorders the tied group."""
        pool = self._make_five_pair_pool()
        ManualPoolTiebreakResolution.objects.create(
            pool=pool, wins_tied_at=2,
            resolved_order=[self.pair_by_seed(4).id, self.pair_by_seed(3).id, self.pair_by_seed(2).id],
            reason='Seed 2 forfeited a game')
        standings = self.impl.get_pool_standings(pool)
        self.assertEqual([e['pair'].seed for e in standings], [1, 4, 3, 2, 5])
        for e in standings:
            if e.get('tied'):
                self.assertTrue(e['manually_resolved'])
                self.assertEqual(e['manual_reason'], 'Seed 2 forfeited a game')
            else:
                self.assertFalse(e.get('manually_resolved'))

    def test_no_tiebreak_info_before_any_games_played(self):
        """Pairs at 0 wins with 0 games played are not presented as a resolved tie."""
        pool_a = self.stages[0].pools.order_by('order').first()
        standings = self.impl.get_pool_standings(pool_a)
        self.assertFalse(any(e.get('tied') for e in standings))
        # Untouched pools keep the seeding order
        self.assertEqual([e['pair'].seed for e in standings], [1, 10, 11, 20])

    def test_manual_resolution_matching_automatic_order_not_flagged(self):
        """A manual resolution that agrees with the automatic order is not marked."""
        pool = self._make_five_pair_pool()
        ManualPoolTiebreakResolution.objects.create(
            pool=pool, wins_tied_at=2,
            resolved_order=[self.pair_by_seed(2).id, self.pair_by_seed(3).id, self.pair_by_seed(4).id],
            reason='')
        standings = self.impl.get_pool_standings(pool)
        self.assertEqual([e['pair'].seed for e in standings], [1, 2, 3, 4, 5])
        self.assertFalse(any(e.get('manually_resolved') for e in standings))


class EurosScoreRulesTest(EurosFormatTestBase):
    """Each phase declares its expected game format for score validation."""

    def test_rules_per_phase(self):
        one_game_to_21 = {'points_to': 21, 'cap': 23, 'best_of': 1}
        self.assertEqual(self.impl.get_score_rules(self.stages[0].matchups.first()),
                         one_game_to_21)
        self.advance_through_phase2()
        self.assertEqual(self.impl.get_score_rules(self.stages[1].matchups.first()),
                         one_game_to_21)

        finals = self.stages[2]
        top_group = finals.pools.get(order=0)
        consolation_group = finals.pools.get(order=1)
        for semi in top_group.matchups.filter(round_number=1):
            self.assertEqual(self.impl.get_score_rules(semi),
                             {'points_to': 15, 'cap': 18, 'best_of': 3})
        for consolation_semi in consolation_group.matchups.filter(round_number=1):
            self.assertEqual(self.impl.get_score_rules(consolation_semi), one_game_to_21)

        self.play_finals()
        final, third_place = top_group.matchups.filter(round_number=2).order_by('court_number')
        self.assertEqual(self.impl.get_score_rules(final),
                         {'points_to': 21, 'cap': 23, 'best_of': 3})
        self.assertEqual(self.impl.get_score_rules(third_place), one_game_to_21)
        for placement in consolation_group.matchups.filter(round_number=2):
            self.assertEqual(self.impl.get_score_rules(placement), one_game_to_21)


class EurosViewsTest(EurosFormatTestBase):
    """The detail page renders (all template branches) and the advancement endpoint works."""

    def setUp(self):
        super().setUp()
        from django.utils import timezone
        self.client = Client()
        self.player_user = User.objects.create_user(
            username='player_test', password='test123', role='PLAYER')
        self.spectator_user = User.objects.create_user(
            username='spectator_test', password='test123', role='SPECTATOR')
        # player_test is competing in this tournament, and the tournament is
        # current, so it may manage results (record / advance phases).
        self.tournament.date = timezone.now().date()
        self.tournament.save()
        self.pairs[0].player1.user = self.player_user
        self.pairs[0].player1.save()
        self.client.login(username='player_test', password='test123')

    def detail(self):
        return self.client.get(reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))

    def test_detail_renders_phase1(self):
        response = self.detail()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pool A')
        self.assertContains(response, 'Pool Phase 2 has not been generated yet')
        self.assertTrue(response.context['is_multi_phase'])
        self.assertFalse(response.context['can_advance_stage'])

    def test_detail_shows_advance_button_when_phase_complete(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        response = self.detail()
        self.assertTrue(response.context['can_advance_stage'])
        self.assertContains(response, 'Generate Pool Phase 2')

    def test_generate_next_stage_endpoint(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        response = self.client.post(
            reverse('generate_next_stage', kwargs={'tournament_id': self.tournament.pk}))
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(self.stages[1].matchups.count(), 90)

    def test_generate_next_stage_blocked_when_incomplete(self):
        response = self.client.post(
            reverse('generate_next_stage', kwargs={'tournament_id': self.tournament.pk}))
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(self.stages[1].matchups.count(), 0)

    def test_generate_next_stage_denied_for_spectator(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(
            reverse('generate_next_stage', kwargs={'tournament_id': self.tournament.pk}))
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(self.stages[1].matchups.count(), 0)

    def test_detail_renders_finals_and_final_standings(self):
        self.advance_through_phase2()
        response = self.detail()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Places 1-4')
        self.assertIsNone(response.context['final_standings'])

        self.play_finals()
        response = self.detail()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['final_standings']), 20)
        self.assertTrue(response.context['tournament_complete'])

    def test_detail_shows_tiebreak_explanation(self):
        """A tie broken by head-to-head is explained in the pool standings table."""
        self.play_stage_lower_seed_wins(self.stages[0])
        response = self.detail()
        # Lower-seed-wins gives every pool distinct win counts except none tied;
        # standings still render the Tiebreak column header.
        self.assertContains(response, '<th>Tiebreak</th>', html=True)

        # Force a tie in Pool A: seed 20 upsets seed 1, so seeds 1 and 10
        # are tied at 2 wins (and seeds 11 and 20 at 1 win)
        pool_a = self.stages[0].pools.order_by('order').first()
        matchups = {frozenset((m.pair1.seed, m.pair2.seed)): m for m in pool_a.matchups.all()}
        self.record_win(matchups[frozenset((1, 20))], self.pair_by_seed(20))
        response = self.detail()
        self.assertContains(response, 'H2H:')

    def test_sandbox_reset_tears_down_generated_phases(self):
        self.tournament.is_sandbox = True
        self.tournament.save()
        self.advance_through_phase2()  # phases 1+2 played, finals semis generated
        self.assertTrue(self.stages[1].matchups.exists())
        self.assertTrue(self.stages[2].pools.exists())

        response = self.client.post(reverse('reset_sandbox_scores',
                                            kwargs={'tournament_id': self.tournament.pk}))
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        self.assertEqual(
            MatchScore.objects.filter(matchup__tournament_chart=self.tournament).count(), 0)
        # Generated later phases are torn down; phase 1 structure survives unscored.
        self.assertFalse(self.stages[1].matchups.exists())
        self.assertFalse(self.stages[1].pools.exists())
        self.assertFalse(self.stages[2].matchups.exists())
        self.assertEqual(self.stages[0].matchups.count(), 30)
        self.assertEqual(self.stages[0].pools.count(), 5)

    def test_record_score_warn_and_confirm(self):
        matchup = self.stages[0].matchups.first()
        url = reverse('record_match_result', kwargs={
            'tournament_id': self.tournament.pk, 'matchup_id': matchup.id})

        # Pool Phase 1 is one game to 21 — a game recorded to 15 gets flagged
        # and nothing is saved yet.
        response = self.client.post(url, {'team1_scores': '[15]', 'team2_scores': '[13]'})
        data = response.json()
        self.assertEqual(data['status'], 'needs_confirmation')
        self.assertTrue(data['warnings'])
        self.assertEqual(matchup.scores.count(), 0)

        # A confirmed resubmit is accepted (forfeits, retirements, ...).
        response = self.client.post(url, {'team1_scores': '[15]', 'team2_scores': '[13]',
                                          'confirmed': '1'})
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(matchup.scores.count(), 1)

        # Conforming scores save without any confirmation round-trip.
        for team1, team2 in [('[21]', '[19]'), ('[22]', '[20]'), ('[23]', '[22]')]:
            response = self.client.post(url, {'team1_scores': team1, 'team2_scores': team2})
            self.assertEqual(response.json()['status'], 'success',
                             f"{team1}–{team2} should be accepted directly")

    def test_manual_tiebreak_page_lists_pool_ties_and_saves(self):
        self.play_stage_lower_seed_wins(self.stages[0])
        pool_a = self.stages[0].pools.order_by('order').first()
        matchups = {frozenset((m.pair1.seed, m.pair2.seed)): m for m in pool_a.matchups.all()}
        # Seed 20 upsets seed 1: seeds 1 and 10 tied at 2 wins
        self.record_win(matchups[frozenset((1, 20))], self.pair_by_seed(20))
        standings = self.impl.get_pool_standings(pool_a)
        self.assertEqual([e['pair'].seed for e in standings], [1, 10, 11, 20])

        url = reverse('manual_tiebreak_resolution', kwargs={'tournament_id': self.tournament.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_multi_phase'])
        ties = response.context['pool_ties']
        self.assertTrue(any(t['pool'].id == pool_a.id and t['wins'] == 2 for t in ties))

        # Save a manual order: seed 10 above seed 1 (automatic gives 1 above 10 on h2h)
        p1, p10 = self.pair_by_seed(1), self.pair_by_seed(10)
        response = self.client.post(url, {
            'pool_id': pool_a.id,
            'wins_level': 2,
            'pair_order': [p10.id, p1.id],
            'reason': 'Forfeit',
        })
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))
        standings = self.impl.get_pool_standings(pool_a)
        self.assertEqual([e['pair'].seed for e in standings], [10, 1, 11, 20])
        self.assertTrue(standings[0]['manually_resolved'])

    def test_my_matches_show_format_for_every_finals_match_type(self):
        """'My matches' labels each finals match with its format: top-group semis
        best-of-3 to 15, the final best-of-3 to 21, and everything else (third
        place, consolation semis, consolation placements) one game to 21."""
        self.advance_through_phase2()
        finals = self.stages[2]

        # With lower-seed-wins throughout, the 'Places 1-4' group holds seeds 1-4
        # (semis 1v4 and 2v3) and 'Places 5-8' holds seeds 5-8. player_test is
        # already linked to seed 1; add viewers for seed 4 (semi loser -> third
        # place) and seed 5 (consolation group).
        for seed in (4, 5):
            user = User.objects.create_user(
                username=f'seed{seed}', password='test123', role='PLAYER')
            player = self.pair_by_seed(seed).player1
            player.user = user
            player.save()

        def my_unplayed(username):
            self.client.login(username=username, password='test123')
            response = self.detail()
            return [(m.round_number, m.score_rules_text)
                    for m in response.context['my_matchups'] if not m.scores.exists()]

        # Semis: best-of-3 in the top group, one game in consolation groups.
        self.assertEqual(my_unplayed('player_test'),
                         [(1, 'Best of 3 to 15, win by 2, cap 18')])
        self.assertEqual(my_unplayed('seed5'),
                         [(1, 'One game to 21, win by 2, cap 23')])

        # Score the semis of both groups; placement matches get auto-generated.
        for pool in finals.pools.filter(order__in=(0, 1)):
            for semi in pool.matchups.filter(round_number=1):
                winner = semi.pair1 if semi.pair1.seed < semi.pair2.seed else semi.pair2
                self.record_win(semi, winner)
                self.impl.maybe_generate_placement_matches(self.tournament, semi)

        # Final (seed 1 won its semi) is best-of-3 to 21; the third-place match
        # (seed 4 lost) and the consolation placement (seed 5) are one game to 21.
        self.assertEqual(my_unplayed('player_test'),
                         [(2, 'Best of 3 to 21, win by 2, cap 23')])
        self.assertEqual(my_unplayed('seed4'),
                         [(2, 'One game to 21, win by 2, cap 23')])
        self.assertEqual(my_unplayed('seed5'),
                         [(2, 'One game to 21, win by 2, cap 23')])


class EurosCreationViewTest(TestCase):
    """Creating a PAIRS tournament with 40 players auto-detects the euros format."""

    def test_create_with_40_players(self):
        client = Client()
        User.objects.create_user(username='player_test', password='test123', role='PLAYER')
        client.login(username='player_test', password='test123')

        players = [
            Player.objects.create(
                first_name=f'F{i}', last_name=f'L{i}', ranking=i, ranking_points=1000 - i)
            for i in range(1, 41)
        ]
        response = client.post(reverse('tournament_create'), data={
            'name': 'EO 2026',
            'date': '2026-07-01',
            'tournament_category': 'PAIRS',
            'number_of_stages': 1,  # overridden by the multi-phase format
            'format_type': 'STANDARD',
            'name_display_format': 'FIRST',
            'players': [p.id for p in players],
        })
        self.assertEqual(response.status_code, 302, getattr(response.context, 'get', lambda k: None)('form'))

        tournament = TournamentChart.objects.latest('id')
        self.assertEqual(tournament.archetype.name, '20 pairs euros format')
        self.assertEqual(tournament.number_of_stages, 3)
        self.assertEqual(tournament.stages.count(), 3)
        stage1 = tournament.stages.get(stage_number=1)
        self.assertEqual(stage1.pools.count(), 5)
        self.assertEqual(stage1.matchups.count(), 30)
        # Later stages exist but have no matchups yet
        self.assertEqual(tournament.stages.get(stage_number=2).matchups.count(), 0)
        self.assertEqual(tournament.stages.get(stage_number=3).matchups.count(), 0)
