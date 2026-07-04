from django.test import TestCase, Client
from django.urls import reverse
from ..models import Player, Pair, TournamentChart, TournamentArchetype, Matchup, MatchScore, Pool, PoolPair, User
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


class EurosViewsTest(EurosFormatTestBase):
    """The detail page renders (all template branches) and the advancement endpoint works."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.player_user = User.objects.create_user(
            username='player_test', password='test123', role='PLAYER')
        self.spectator_user = User.objects.create_user(
            username='spectator_test', password='test123', role='SPECTATOR')
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
