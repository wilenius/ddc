from django.db import models
from .base_models import TournamentArchetype, Matchup, Pair, Player, Stage, Pool, PoolPair
from typing import List, Dict, Optional, Any

# Function to map TournamentArchetype database objects to their code implementations
def get_implementation(archetype: TournamentArchetype) -> Optional[Any]:
    """
    Maps a TournamentArchetype database object to its code implementation.
    """
    # For now we use a simple name-based mapping
    implementations = {
        # Doubles/Pairs tournaments
        "2 pairs doubles tournament": TwoPairsFormat(),
        "3 pairs doubles tournament": ThreePairsFormat(),
        "4 pairs doubles tournament": FourPairsSwedishFormat(),
        "5 pairs doubles tournament": FivePairsFormat(),
        "6 pairs doubles tournament": SixPairsFormat(),
        "7 pairs doubles tournament": SevenPairsFormat(),
        "8 pairs doubles tournament": EightPairsSwedishFormat(),
        "9 pairs doubles tournament": NinePairsFormat(),
        "10 pairs doubles tournament": TenPairsFormat(),
        "20 pairs euros format": EurosFormat(),
        # Monarch of the Court tournaments
        "5-player Monarch of the Court": MonarchOfTheCourt5(),
        "6-player Monarch of the Court": MonarchOfTheCourt6(),
        "7-player Monarch of the Court": MonarchOfTheCourt7(),
        "8-player Monarch of the Court": MonarchOfTheCourt8(),
        "9-player Monarch of the Court": MonarchOfTheCourt9(),
        "10-player Monarch of the Court": MonarchOfTheCourt10(),
        "11-player Monarch of the Court": MonarchOfTheCourt11(),
        "12-player Monarch of the Court": MonarchOfTheCourt12(),
        "13-player Monarch of the Court": MonarchOfTheCourt13(),
        "14-player Monarch of the Court": MonarchOfTheCourt14(),
        "15-player Monarch of the Court": MonarchOfTheCourt15(),
        "16-player Monarch of the Court": MonarchOfTheCourt16(),
    }
    
    return implementations.get(archetype.name)

# Base for Swedish pairs tournaments
class PairsTournamentArchetype(TournamentArchetype):
    class Meta:
        abstract = True
    tournament_category = 'PAIRS'
    number_of_pairs: int = None
    number_of_fields: int = None
    schedule: List[List[tuple]] = []  # e.g., [[(1,3),(2,4)], ...]

    def calculate_rounds(self, num_pairs: int):
        return len(self.schedule)

    def calculate_courts(self, num_pairs: int):
        return self.number_of_fields

    def generate_matchups(self, tournament_chart, pairs: List[Pair], stage=None):
        # Map pairs to seeds 1-based
        if len(pairs) != self.number_of_pairs:
            raise ValueError(f"This tournament format requires exactly {self.number_of_pairs} pairs")
        pairs_by_seed = {pair.seed: pair for pair in pairs}
        for round_idx, round_matches in enumerate(self.schedule, 1):
            for field_idx, (seed1, seed2) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1=pairs_by_seed[seed1],
                    pair2=pairs_by_seed[seed2],
                    round_number=round_idx,
                    court_number=field_idx
                )

class TwoPairsFormat(PairsTournamentArchetype):
    number_of_pairs = 2
    number_of_fields = 1
    schedule = [
        [(1, 2)],
    ]
    name = "2 pairs doubles tournament"
    description = "Best-of-5 format: 1 match with 2 pairs."

class ThreePairsFormat(PairsTournamentArchetype):
    number_of_pairs = 3
    number_of_fields = 1
    schedule = [
        [(1, 3)],
        [(2, 3)],
        [(1, 2)],
    ]
    name = "3 pairs doubles tournament"
    description = "Round robin: 3 rounds on 1 court with 3 pairs."

class FourPairsSwedishFormat(PairsTournamentArchetype):
    number_of_pairs = 4
    number_of_fields = 2
    schedule = [
        [(1, 3), (2, 4)],
        [(1, 4), (2, 3)],
        [(1, 2), (3, 4)],
    ]
    name = "4 pairs doubles tournament"
    description = "Round robin: 3 rounds on 2 courts with 4 pairs."

class FivePairsFormat(PairsTournamentArchetype):
    number_of_pairs = 5
    number_of_fields = 2
    schedule = [
        [(1, 5), (2, 4)],
        [(1, 3), (4, 5)],
        [(2, 5), (3, 4)],
        [(1, 4), (2, 3)],
        [(1, 2), (3, 5)],
    ]
    name = "5 pairs doubles tournament"
    description = "Round robin: 5 rounds on 2 courts with 5 pairs."

class SixPairsFormat(PairsTournamentArchetype):
    number_of_pairs = 6
    number_of_fields = 3
    schedule = [
        [(1, 5), (2, 4), (3, 6)],
        [(1, 6), (2, 5), (3, 4)],
        [(1, 3), (2, 6), (4, 5)],
        [(1, 4), (2, 3), (5, 6)],
        [(1, 2), (3, 5), (4, 6)],
    ]
    name = "6 pairs doubles tournament"
    description = "Round robin: 5 rounds on 3 courts with 6 pairs."

class SevenPairsFormat(PairsTournamentArchetype):
    number_of_pairs = 7
    number_of_fields = 3
    schedule = [
        [(1, 5), (2, 6), (3, 7)],
        [(1, 6), (2, 5), (4, 7)],
        [(1, 7), (3, 5), (4, 6)],
        [(2, 7), (3, 6), (4, 5)],
        [(1, 4), (2, 3), (6, 7)],
        [(1, 3), (2, 4), (5, 7)],
        [(1, 2), (3, 4), (5, 6)],
    ]
    name = "7 pairs doubles tournament"
    description = "Round robin: 7 rounds on 3 courts with 7 pairs."

class EightPairsSwedishFormat(PairsTournamentArchetype):
    number_of_pairs = 8
    number_of_fields = 4
    schedule = [
        [(1, 5), (2, 6), (3, 7), (4, 8)],
        [(1, 6), (2, 5), (3, 8), (4, 7)],
        [(1, 7), (2, 8), (3, 5), (4, 6)],
        [(1, 8), (2, 7), (3, 6), (4, 5)],
        [(1, 3), (2, 4), (5, 7), (6, 8)],
        [(1, 4), (2, 3), (5, 8), (6, 7)],
        [(1, 2), (3, 4), (5, 6), (7, 8)],
    ]
    name = "8 pairs doubles tournament"
    description = "Round robin: 7 rounds on 4 courts with 8 pairs."

class NinePairsFormat(PairsTournamentArchetype):
    number_of_pairs = 9
    number_of_fields = 4
    schedule = [
        [(1, 9), (2, 8), (3, 7), (4, 6)],
        [(2, 9), (3, 8), (4, 7), (5, 6)],
        [(1, 8), (2, 7), (3, 6), (4, 5)],
        [(1, 7), (2, 6), (3, 5), (8, 9)],
        [(1, 6), (2, 5), (3, 4), (7, 9)],
        [(1, 5), (2, 4), (6, 9), (7, 8)],
        [(1, 4), (2, 3), (5, 9), (6, 8)],
        [(1, 3), (4, 9), (5, 8), (6, 7)],
        [(1, 2), (4, 8), (3, 9), (5, 7)],
    ]
    name = "9 pairs doubles tournament"
    description = "Round robin: 9 rounds on 4 courts with 9 pairs."

class TenPairsFormat(PairsTournamentArchetype):
    number_of_pairs = 10
    number_of_fields = 5
    schedule = [
        [(1, 9), (2, 8), (3, 7), (4, 6), (5, 10)],
        [(1, 10), (2, 9), (3, 8), (4, 7), (5, 6)],
        [(1, 8), (2, 7), (3, 6), (4, 5), (9, 10)],
        [(1, 7), (2, 6), (3, 5), (4, 10), (8, 9)],
        [(1, 6), (2, 5), (3, 4), (7, 9), (8, 10)],
        [(1, 5), (2, 4), (3, 10), (6, 9), (7, 8)],
        [(1, 4), (2, 3), (5, 9), (6, 8), (7, 10)],
        [(1, 3), (2, 10), (4, 9), (5, 8), (6, 7)],
        [(1, 2), (4, 8), (3, 9), (5, 7), (6, 10)],
    ]
    name = "10 pairs doubles tournament"
    description = "Round robin: 9 rounds on 5 courts with 10 pairs."

class EurosFormat(PairsTournamentArchetype):
    """
    'Euros' format for 20 pairs (used at European Open 2024/2026).

    Phase 1: 5 pools of 4 (snake seeding), single round robin within each pool.
    Phase 2: top 2 of each pool -> A Pool (10 pairs), bottom 2 -> B Pool (10 pairs),
             full round robin within each pool (former pool-mates play again).
    Finals:  provisional order (A Pool ranks 1-10, B Pool ranks 11-20) is sliced into
             groups of 4 (1-4, 5-8, ...). Each group plays semis (1v4, 2v3), then the
             winners play a placement final and the losers a consolation match.
    Every pair plays 3 + 9 + 2 = 14 matches.

    Phases 2 and 3 depend on earlier results, so their matchups are generated via
    advance_to_next_stage() once the previous stage is complete.
    """
    name = "20 pairs euros format"
    description = "Euros format: 5 pools of 4, then A/B pools of 10, then placement groups of 4."
    number_of_pairs = 20
    number_of_fields = 10
    is_multi_phase = True

    STAGE_DEFINITIONS = [
        {'stage_number': 1, 'stage_type': 'POOL', 'name': 'Pool Phase 1'},
        {'stage_number': 2, 'stage_type': 'POOL', 'name': 'Pool Phase 2'},
        {'stage_number': 3, 'stage_type': 'PLAYOFF', 'name': 'Finals'},
    ]

    NUM_FIRST_PHASE_POOLS = 5

    def calculate_rounds(self, num_pairs):
        return 14  # 3 (phase 1) + 9 (phase 2) + 2 (finals)

    def calculate_courts(self, num_pairs):
        return self.number_of_fields

    def get_score_rules(self, matchup):
        """Euros match formats (all games win by 2):
        One game to 21, cap 23, everywhere — pool phases, consolation semis,
        placement matches, and the third-place playoff — except in the
        "Places 1-4" group: its semis are best-of-3 to 15 (cap 18) and its
        final is best-of-3 to 21 (cap 23).
        """
        if matchup.stage is None:
            return None
        one_game_to_21 = {'points_to': 21, 'cap': 23, 'best_of': 1}
        if matchup.stage.stage_number != 3:
            return one_game_to_21
        if matchup.pool is None or matchup.pool.order != 0:
            return one_game_to_21
        if matchup.round_number == 1:
            return {'points_to': 15, 'cap': 18, 'best_of': 3}
        # Round 2: the winners' match (the final) is on the odd court,
        # the losers' match (third-place playoff) on the even one.
        if matchup.court_number % 2 == 1:
            return {'points_to': 21, 'cap': 23, 'best_of': 3}
        return one_game_to_21

    def create_stages(self, tournament) -> List[Stage]:
        """Create the three stages. Each stage's standings are computed from its own matches."""
        return [
            Stage.objects.create(tournament=tournament, scoring_mode='RESET', **definition)
            for definition in self.STAGE_DEFINITIONS
        ]

    def generate_matchups(self, tournament_chart, pairs: List[Pair], stage=None):
        """Generate phase 1: snake-seed 20 pairs into 5 pools of 4, round robin in each."""
        if len(pairs) != self.number_of_pairs:
            raise ValueError(f"This tournament format requires exactly {self.number_of_pairs} pairs")
        if stage is None:
            raise ValueError("The euros format requires a stage for matchup generation")

        sorted_pairs = sorted(pairs, key=lambda p: p.seed)

        # Snake seeding: seeds 1-5 go to pools A-E, 6-10 to E-A, 11-15 to A-E, 16-20 to E-A.
        pool_members = [[] for _ in range(self.NUM_FIRST_PHASE_POOLS)]
        for block_idx in range(0, len(sorted_pairs), self.NUM_FIRST_PHASE_POOLS):
            block = sorted_pairs[block_idx:block_idx + self.NUM_FIRST_PHASE_POOLS]
            if (block_idx // self.NUM_FIRST_PHASE_POOLS) % 2 == 1:
                block = list(reversed(block))
            for pool_idx, pair in enumerate(block):
                pool_members[pool_idx].append(pair)

        for pool_idx, members in enumerate(pool_members):
            pool = self._create_pool(
                stage,
                name=f"Pool {chr(ord('A') + pool_idx)}",
                order=pool_idx,
                ordered_pairs=members,
            )
            self._generate_pool_round_robin(
                tournament_chart, stage, pool, members,
                schedule=FourPairsSwedishFormat.schedule,
                court_offset=pool_idx * 2,
            )

    def advance_to_next_stage(self, tournament) -> Stage:
        """
        Generate the next stage's matchups from the previous stage's results.
        Raises ValueError if the previous stage is incomplete or everything is generated.
        Returns the stage that was populated.
        """
        stages = list(tournament.stages.order_by('stage_number'))
        if len(stages) != 3:
            raise ValueError("This tournament does not have the expected three stages")
        stage1, stage2, stage3 = stages

        if not stage2.matchups.exists():
            if not self.is_stage_complete(stage1):
                raise ValueError(f"{stage1.name} is not complete yet - record all scores first")
            self._generate_second_phase(tournament, stage1, stage2)
            return stage2
        elif not stage3.matchups.exists():
            if not self.is_stage_complete(stage2):
                raise ValueError(f"{stage2.name} is not complete yet - record all scores first")
            self._generate_finals(tournament, stage2, stage3)
            return stage3
        else:
            raise ValueError("All stages have already been generated")

    def get_next_stage_to_generate(self, tournament) -> Optional[Stage]:
        """Returns the first stage without matchups, or None if all are generated."""
        return tournament.stages.filter(matchups__isnull=True).order_by('stage_number').first()

    def is_stage_complete(self, stage) -> bool:
        """A stage is complete when it has matchups and every matchup has a recorded score."""
        matchups = stage.matchups.annotate(num_scores=models.Count('scores'))
        return matchups.exists() and not matchups.filter(num_scores=0).exists()

    def _generate_second_phase(self, tournament, stage1, stage2):
        """Top 2 of each phase-1 pool -> A Pool, bottom 2 -> B Pool; fresh 10-team round robins."""
        rankings = [
            [entry['pair'] for entry in self.get_pool_standings(pool)]
            for pool in stage1.pools.order_by('order')
        ]
        # Pool-internal seeding: pool winners first (in pool order), then runners-up, etc.
        a_pool_pairs = [r[0] for r in rankings] + [r[1] for r in rankings]
        b_pool_pairs = [r[2] for r in rankings] + [r[3] for r in rankings]

        for order, (name, members, court_offset) in enumerate([
            ("A Pool", a_pool_pairs, 0),
            ("B Pool", b_pool_pairs, 5),
        ]):
            pool = self._create_pool(stage2, name=name, order=order, ordered_pairs=members)
            self._generate_pool_round_robin(
                tournament, stage2, pool, members,
                schedule=TenPairsFormat.schedule,
                court_offset=court_offset,
            )

    def _generate_finals(self, tournament, stage2, stage3):
        """Slice the provisional order into groups of 4; each group plays semis 1v4 and 2v3."""
        a_pool, b_pool = list(stage2.pools.order_by('order'))
        provisional_order = (
            [entry['pair'] for entry in self.get_pool_standings(a_pool)]
            + [entry['pair'] for entry in self.get_pool_standings(b_pool)]
        )

        for group_idx in range(5):
            base = group_idx * 4
            group = provisional_order[base:base + 4]
            pool = self._create_pool(
                stage3,
                name=f"Places {base + 1}-{base + 4}",
                order=group_idx,
                ordered_pairs=group,
            )
            # Semifinals: 1v4 and 2v3 (positions within the group)
            Matchup.objects.create(
                tournament_chart=tournament, stage=stage3, pool=pool,
                pair1=group[0], pair2=group[3],
                round_number=1, court_number=group_idx * 2 + 1,
            )
            Matchup.objects.create(
                tournament_chart=tournament, stage=stage3, pool=pool,
                pair1=group[1], pair2=group[2],
                round_number=1, court_number=group_idx * 2 + 2,
            )

    def maybe_generate_placement_matches(self, tournament, matchup):
        """
        Called after a score is recorded. If both semifinals of a finals group are now
        scored and the placement matches don't exist yet, create them (winners play for
        the higher placement, losers for the lower).
        """
        pool = matchup.pool
        if pool is None or matchup.stage is None or matchup.stage.stage_type != 'PLAYOFF':
            return
        if pool.matchups.filter(round_number=2).exists():
            return
        semis = list(pool.matchups.filter(round_number=1).order_by('court_number'))
        if len(semis) != 2 or any(not semi.scores.exists() for semi in semis):
            return

        winner1, loser1 = self._matchup_winner_loser(semis[0])
        winner2, loser2 = self._matchup_winner_loser(semis[1])
        Matchup.objects.create(
            tournament_chart=tournament, stage=matchup.stage, pool=pool,
            pair1=winner1, pair2=winner2,
            round_number=2, court_number=semis[0].court_number,
        )
        Matchup.objects.create(
            tournament_chart=tournament, stage=matchup.stage, pool=pool,
            pair1=loser1, pair2=loser2,
            round_number=2, court_number=semis[1].court_number,
        )

    def get_pool_standings(self, pool) -> List[Dict]:
        """
        Rank the pairs in a pool by this pool's matches only, breaking win ties
        with the DDC doubles tiebreak rules:
          Step 1: fewest forfeits — TODO: forfeits cannot be recorded yet; once
                  they can, apply this before the head-to-head steps.
          Step 2: record against the other tied teams
          Step 3: point differential against the other tied teams
          Step 4: record against teams placed above the tied group
          Step 5: point differential against teams placed above the tied group
          Step 6: point differential against all teams in the pool
          Step 7: manual resolution by the director (ManualPoolTiebreakResolution),
                  applied on top of the automatic order; original seed is the
                  last automatic resort.
        Returns a list of dicts: {'pair', 'wins', 'matches_played', 'point_difference',
        'position'}, plus tiebreak stats ('h2h_wins', 'h2h_losses', 'h2h_pd',
        'above_wins', 'above_pd', 'manually_resolved', 'manual_reason') on tied entries.
        """
        members = [pp.pair for pp in PoolPair.objects.filter(pool=pool).select_related(
            'pair', 'pair__player1', 'pair__player2').order_by('position')]
        stats = {pair.id: {'pair': pair, 'wins': 0, 'matches_played': 0, 'point_difference': 0}
                 for pair in members}

        scored_matchups = []
        for m in pool.matchups.select_related('pair1', 'pair2').prefetch_related('scores'):
            scores = list(m.scores.all())
            if not scores:
                continue
            scored_matchups.append(m)
            winner, _ = self._matchup_winner_loser(m, scores)
            pair1_pd = sum(s.point_difference if s.winning_team == 1 else -s.point_difference
                           for s in scores)
            stats[m.pair1_id]['matches_played'] += 1
            stats[m.pair2_id]['matches_played'] += 1
            stats[m.pair1_id]['point_difference'] += pair1_pd
            stats[m.pair2_id]['point_difference'] -= pair1_pd
            stats[winner.id]['wins'] += 1

        # Base order: wins desc, then PD desc, then seed asc
        ordered = sorted(stats.values(),
                         key=lambda e: (-e['wins'], -e['point_difference'], e['pair'].seed))

        # Refine tie groups (same wins) with the tiebreak steps
        result = []
        idx = 0
        while idx < len(ordered):
            group = [ordered[idx]]
            while idx + len(group) < len(ordered) and ordered[idx + len(group)]['wins'] == group[0]['wins']:
                group.append(ordered[idx + len(group)])
            if len(group) > 1:
                above_ids = {entry['pair'].id for entry in ordered[:idx]}
                group = self._sort_tied_group(group, scored_matchups, above_ids, pool)
            result.extend(group)
            idx += len(group)

        for position, entry in enumerate(result, start=1):
            entry['position'] = position
        return result

    def _sort_tied_group(self, group, scored_matchups, above_ids, pool):
        """
        Sort a group of entries tied on wins, per the DDC doubles tiebreak rules
        (see get_pool_standings). Annotates each entry with the stats used so the
        UI can show how the tie was resolved.
        """
        tied_ids = {entry['pair'].id for entry in group}
        records = {pair_id: {'h2h_wins': 0, 'h2h_losses': 0, 'h2h_pd': 0,
                             'above_wins': 0, 'above_pd': 0}
                   for pair_id in tied_ids}
        for m in scored_matchups:
            in1, in2 = m.pair1_id in tied_ids, m.pair2_id in tied_ids
            if not (in1 or in2):
                continue
            scores = list(m.scores.all())
            winner, loser = self._matchup_winner_loser(m, scores)
            pair1_pd = sum(s.point_difference if s.winning_team == 1 else -s.point_difference
                           for s in scores)
            # Steps 2-3: games among the tied teams
            if in1 and in2:
                records[winner.id]['h2h_wins'] += 1
                records[loser.id]['h2h_losses'] += 1
                records[m.pair1_id]['h2h_pd'] += pair1_pd
                records[m.pair2_id]['h2h_pd'] -= pair1_pd
            # Steps 4-5: games against teams that placed above the tied group
            elif in1 and m.pair2_id in above_ids:
                if winner.id == m.pair1_id:
                    records[m.pair1_id]['above_wins'] += 1
                records[m.pair1_id]['above_pd'] += pair1_pd
            elif in2 and m.pair1_id in above_ids:
                if winner.id == m.pair2_id:
                    records[m.pair2_id]['above_wins'] += 1
                records[m.pair2_id]['above_pd'] -= pair1_pd

        # Pairs that haven't played yet are only nominally tied — don't show
        # tiebreak info for them
        for entry in group:
            if entry['matches_played']:
                entry['tied'] = True
                entry.update(records[entry['pair'].id])
        group = sorted(group, key=lambda e: (
            -records[e['pair'].id]['h2h_wins'],      # Step 2
            -records[e['pair'].id]['h2h_pd'],        # Step 3
            -records[e['pair'].id]['above_wins'],    # Step 4
            -records[e['pair'].id]['above_pd'],      # Step 5
            -e['point_difference'],                  # Step 6
            e['pair'].seed,
        ))

        # Step 7: manual resolution by the director overrides the automatic order
        from .scoring import ManualPoolTiebreakResolution
        resolution = ManualPoolTiebreakResolution.objects.filter(
            pool=pool, wins_tied_at=group[0]['wins']).first()
        if resolution:
            auto_order = [e['pair'].id for e in group]
            rank = {pair_id: i for i, pair_id in enumerate(resolution.resolved_order)}
            group = sorted(group, key=lambda e: rank.get(e['pair'].id, len(rank)))
            order_differs = auto_order != [e['pair'].id for e in group]
            for entry in group:
                entry['manually_resolved'] = order_differs
                entry['manual_reason'] = resolution.reason if order_differs else ''
        else:
            # Entries level on every automatic criterion are ordered by seed
            # alone — the rules resolve that with a disc flip, so flag them for
            # the pre-advancement warning (get_unresolved_seed_ties).
            def auto_key(entry):
                r = records[entry['pair'].id]
                return (r['h2h_wins'], r['h2h_pd'], r['above_wins'], r['above_pd'],
                        entry['point_difference'])
            for a, b in zip(group, group[1:]):
                if a['matches_played'] and b['matches_played'] and auto_key(a) == auto_key(b):
                    a['seed_decided'] = b['seed_decided'] = True
        return group

    def get_unresolved_seed_ties(self, stage) -> List[Dict]:
        """
        Tie groups in ``stage`` whose order is currently decided by seed alone
        (every automatic tiebreak criterion is level — the rules call for a disc
        flip) and that have no manual resolution saved. Shown as a warning before
        the next phase is generated from these standings.
        Returns a list of {'pool', 'wins', 'pairs'} in pool order.
        """
        ties = []
        for pool in stage.pools.order_by('order'):
            by_wins = {}
            for entry in self.get_pool_standings(pool):
                if entry.get('seed_decided'):
                    by_wins.setdefault(entry['wins'], []).append(entry['pair'])
            for wins, pairs in sorted(by_wins.items(), reverse=True):
                ties.append({'pool': pool, 'wins': wins, 'pairs': pairs})
        return ties

    def get_final_standings(self, tournament) -> Optional[List[Dict]]:
        """
        Final placements 1-20 once all finals placement matches are played.
        Returns a list of dicts {'position', 'pair'}, or None if the finals aren't done.
        """
        stage3 = tournament.stages.filter(stage_number=3).first()
        if stage3 is None or not stage3.matchups.exists():
            return None

        standings = []
        for group_idx, pool in enumerate(stage3.pools.order_by('order')):
            placement_matches = list(pool.matchups.filter(round_number=2).order_by('court_number'))
            if len(placement_matches) != 2 or any(not m.scores.exists() for m in placement_matches):
                return None
            base = group_idx * 4
            final, consolation = placement_matches
            final_winner, final_loser = self._matchup_winner_loser(final)
            consolation_winner, consolation_loser = self._matchup_winner_loser(consolation)
            standings.extend([
                {'position': base + 1, 'pair': final_winner},
                {'position': base + 2, 'pair': final_loser},
                {'position': base + 3, 'pair': consolation_winner},
                {'position': base + 4, 'pair': consolation_loser},
            ])
        return standings

    def _create_pool(self, stage, name, order, ordered_pairs) -> Pool:
        pool = Pool.objects.create(stage=stage, name=name, order=order)
        for position, pair in enumerate(ordered_pairs, start=1):
            PoolPair.objects.create(pool=pool, pair=pair, position=position)
        return pool

    def _generate_pool_round_robin(self, tournament_chart, stage, pool, ordered_pairs,
                                   schedule, court_offset):
        """Create matchups for a pool using a schedule of pool-internal seed positions."""
        pairs_by_position = {position: pair for position, pair in enumerate(ordered_pairs, start=1)}
        for round_idx, round_matches in enumerate(schedule, 1):
            for match_idx, (pos1, pos2) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pool=pool,
                    pair1=pairs_by_position[pos1],
                    pair2=pairs_by_position[pos2],
                    round_number=round_idx,
                    court_number=court_offset + match_idx,
                )

    def _matchup_winner_loser(self, matchup, scores=None):
        """
        Winning pair of a matchup, mirroring record_match_result: most sets won,
        then total points, then the first set as the last resort.
        """
        if scores is None:
            scores = list(matchup.scores.order_by('set_number'))
        if not scores:
            raise ValueError(f"Matchup {matchup.id} has no recorded scores")
        team1_sets = sum(1 for s in scores if s.winning_team == 1)
        team2_sets = len(scores) - team1_sets
        if team1_sets != team2_sets:
            team1_won = team1_sets > team2_sets
        else:
            team1_points = sum(s.team1_score for s in scores)
            team2_points = sum(s.team2_score for s in scores)
            if team1_points != team2_points:
                team1_won = team1_points > team2_points
            else:
                team1_won = scores[0].winning_team == 1
        if team1_won:
            return matchup.pair1, matchup.pair2
        return matchup.pair2, matchup.pair1

# -- Monarch of the Court base --
class MoCTournamentArchetype(TournamentArchetype):
    class Meta:
        abstract = True
    tournament_category = 'MOC'

    def get_automatic_wins(self, num_players):
        """
        Returns a dict mapping player seed (0-indexed) to number of automatic wins.
        Some formats give automatic wins to top seeds to balance the schedule.
        """
        return {}

# Existing Cade Loving's (now Monarch of the Court) format:
class MonarchOfTheCourt8(MoCTournamentArchetype):
    # Remove abstract=True to allow instantiation
    name = "8-player Monarch of the Court"  # Exact match to migration
    description = "MoC: 8-player specific schedule."

    def calculate_rounds(self, num_players):
        if num_players != 8:
            raise ValueError("This tournament type requires exactly 8 players")
        return 7

    def calculate_courts(self, num_players):
        return 2

    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 8:
            raise ValueError("This tournament type requires exactly 8 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 8-player format from kodiak_formats.md
        schedule = [
            # Round 1: Court 1: 1&3 vs 6&8 (4 v 14), Court 2: 2&4 vs 5&7 (6 v 12)
            [(0, 2, 5, 7, 1), (1, 3, 4, 6, 2)],
            # Round 2: Court 1: 1&6 vs 4&7 (7 v 11), Court 2: 3&8 vs 2&5 (11 v 7)
            [(0, 5, 3, 6, 1), (2, 7, 1, 4, 2)],
            # Round 3: Court 1: 1&2 vs 7&8 (3 v 15), Court 2: 3&4 vs 5&6 (7 v 11)
            [(0, 1, 6, 7, 1), (2, 3, 4, 5, 2)],
            # Round 4: Court 1: 1&5 vs 2&6 (6 v 8), Court 2: 4&8 vs 3&7 (12 v 10)
            [(0, 4, 1, 5, 1), (3, 7, 2, 6, 2)],
            # Round 5: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2)],
            # Round 6: Court 1: 1&7 vs 3&5 (8 v 8), Court 2: 4&6 vs 2&8 (10 v 10)
            [(0, 6, 2, 4, 1), (3, 5, 1, 7, 2)],
            # Round 7: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 6&7 vs 5&8 (13 v 13)
            [(0, 3, 1, 2, 1), (5, 6, 4, 7, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )

# 5-player Monarch of the Court (Option A)
class MonarchOfTheCourt5(MoCTournamentArchetype):
    name = "5-player Monarch of the Court"
    description = "MoC: 5-player specific schedule (Option A)."
    
    def calculate_rounds(self, num_players):
        if num_players != 5:
            raise ValueError("This tournament type requires exactly 5 players")
        return 5
    
    def calculate_courts(self, num_players):
        return 1
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 5:
            raise ValueError("This tournament type requires exactly 5 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 5-player Option A format
        schedule = [
            # Round 1: 1&2 vs 3&5 (3 v 8)
            [(0, 1, 2, 4)],
            # Round 2: 1&3 vs 4&5 (4 v 9)
            [(0, 2, 3, 4)],
            # Round 3: 1&5 vs 3&4 (7 v 7)
            [(0, 4, 2, 3)],
            # Round 4: 1&5 vs 2&4 (6 v 6)
            [(0, 4, 1, 3)],
            # Round 5: 1&4 vs 2&3 (5 v 5)
            [(0, 3, 1, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for field_idx, (p1, p2, p3, p4) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=field_idx
                )

# 6-player Monarch of the Court (Option A)
class MonarchOfTheCourt6(MoCTournamentArchetype):
    name = "6-player Monarch of the Court"
    description = "MoC: 6-player specific schedule (Option A)."
    
    def calculate_rounds(self, num_players):
        if num_players != 6:
            raise ValueError("This tournament type requires exactly 6 players")
        return 7
    
    def calculate_courts(self, num_players):
        return 1
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 6:
            raise ValueError("This tournament type requires exactly 6 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 6-player Option A format
        schedule = [
            # Round 1: 1&3 vs 5&6 (4 v 11)
            [(0, 2, 4, 5)],
            # Round 2: 1&2 vs 3&4 (3 v 7)
            [(0, 1, 2, 3)],
            # Round 3: 3&5 vs 2&6 (8 v 8)
            [(2, 4, 1, 5)],
            # Round 4: 1&5 vs 2&4 (6 v 6)
            [(0, 4, 1, 3)],
            # Round 5: 4&5 vs 3&6 (9 v 9)
            [(3, 4, 2, 5)],
            # Round 6: 1&6 vs 2&5 (7 v 7)
            [(0, 5, 1, 4)],
            # Round 7: 1&4 vs 2&3 (5 v 5)
            [(0, 3, 1, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for field_idx, (p1, p2, p3, p4) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=field_idx
                )
                
# 7-player Monarch of the Court
class MonarchOfTheCourt7(MoCTournamentArchetype):
    name = "7-player Monarch of the Court"
    description = "MoC: 7-player specific schedule."

    def calculate_rounds(self, num_players):
        if num_players != 7:
            raise ValueError("This tournament type requires exactly 7 players")
        return 10

    def calculate_courts(self, num_players):
        return 1

    def get_automatic_wins(self, num_players):
        return {0: 1, 1: 1}
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 7:
            raise ValueError("This tournament type requires exactly 7 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 7-player format
        schedule = [
            # Round 1: 4&6 vs 3&7 (10 v 10)
            [(3, 5, 2, 6)],
            # Round 2: 1&5 vs 2&4 (6 v 6)
            [(0, 4, 1, 3)],
            # Round 3: 2&5 vs 6&7 (7 v 13)
            [(1, 4, 5, 6)],
            # Round 4: 1&7 vs 4&5 (8 v 9)
            [(0, 6, 3, 4)],
            # Round 5: 2&6 vs 3&5 (8 v 8)
            [(1, 5, 2, 4)],
            # Round 6: 1&6 vs 3&4 (7 v 7)
            [(0, 5, 2, 3)],
            # Round 7: 1&3 vs 5&7 (3 v 12)
            [(0, 2, 4, 6)],
            # Round 8: 2&7 vs 3&6 (9 v 9)
            [(1, 6, 2, 5)],
            # Round 9: 5&6 vs 4&7 (11 v 11)
            [(4, 5, 3, 6)],
            # Round 10: 1&4 vs 2&3 (5 v 5)
            [(0, 3, 1, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for field_idx, (p1, p2, p3, p4) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=field_idx
                )
                
# 9-player Monarch of the Court
class MonarchOfTheCourt9(MoCTournamentArchetype):
    name = "9-player Monarch of the Court"
    description = "MoC: 9-player specific schedule with 2 courts."
    
    def calculate_rounds(self, num_players):
        if num_players != 9:
            raise ValueError("This tournament type requires exactly 9 players")
        return 10
    
    def calculate_courts(self, num_players):
        return 2
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 9:
            raise ValueError("This tournament type requires exactly 9 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 9-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 4&9 vs 5&8 (13 v 13), Court 2: X
            [(3, 8, 4, 7, 1)],
            # Round 2: Court 1: 1&2 vs 8&9 (3 v 17), Court 2: 3&4 vs 5&7 (7 v 12)
            [(0, 1, 7, 8, 1), (2, 3, 4, 6, 2)],
            # Round 3: Court 1: 1&3 vs 6&8 (4 v 14), Court 2: 2&5 vs 7&9 (7 v 16)
            [(0, 2, 5, 7, 1), (1, 4, 6, 8, 2)],
            # Round 4: Court 1: 1&9 vs 3&7 (10 v 10), Court 2: 2&8 vs 4&6 (10 v 10)
            [(0, 8, 2, 6, 1), (1, 7, 3, 5, 2)],
            # Round 5: Court 1: 2&9 vs 3&8 (11 v 11), Court 2: 4&7 vs 5&6 (11 v 11)
            [(1, 8, 2, 7, 1), (3, 6, 4, 5, 2)],
            # Round 6: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2)],
            # Round 7: Court 1: 1&7 vs 2&6 (8 v 8), Court 2: 3&9 vs 4&8 (12 v 12)
            [(0, 6, 1, 5, 1), (2, 8, 3, 7, 2)],
            # Round 8: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: 6&9 vs 7&8 (15 v 15)
            [(0, 4, 1, 3, 1), (5, 8, 6, 7, 2)],
            # Round 9: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 5&9 vs 6&7 (14 v 13)
            [(0, 3, 1, 2, 1), (4, 8, 5, 6, 2)],
            # Round 10: Court 1: 1&6 vs 3&5 (7 v 8), Court 2: X
            [(0, 5, 2, 4, 1)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 10-player Monarch of the Court
class MonarchOfTheCourt10(MoCTournamentArchetype):
    name = "10-player Monarch of the Court"
    description = "MoC: 10-player specific schedule with 2 courts."

    def calculate_rounds(self, num_players):
        if num_players != 10:
            raise ValueError("This tournament type requires exactly 10 players")
        return 11

    def calculate_courts(self, num_players):
        return 2

    def get_automatic_wins(self, num_players):
        return {0: 1, 1: 1}
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 10:
            raise ValueError("This tournament type requires exactly 10 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 10-player format
        schedule = [
            # Round 1: Court 1: 1&3 vs 6&9 (4 v 15), Court 2: 2&5 vs 8&10 (7 v 18)
            [(0, 2, 5, 8, 1), (1, 4, 7, 9, 2)],
            # Round 2: Court 1: 1&7 vs 3&4 (8 v 7), Court 2: 6&8 vs 5&10 (14 v 15)
            [(0, 6, 2, 3, 1), (5, 7, 4, 9, 2)],
            # Round 3: Court 1: 2&6 vs 3&5 (8 v 8), Court 2: 4&7 vs 9&10 (11 v 19)
            [(1, 5, 2, 4, 1), (3, 6, 8, 9, 2)],
            # Round 4: Court 1: 1&6 vs 7&8 (7 v 15), Court 2: 5&9 vs 4&10 (14 v 14)
            [(0, 5, 6, 7, 1), (4, 8, 3, 9, 2)],
            # Round 5: Court 1: 2&10 vs 3&9 (12 v 12), Court 2: 4&8 vs 5&7 (12 v 12)
            [(1, 9, 2, 8, 1), (3, 7, 4, 6, 2)],
            # Round 6: Court 1: 1&9 vs 4&6 (10 v 10), Court 2: 2&8 vs 3&7 (10 v 10)
            [(0, 8, 3, 5, 1), (1, 7, 2, 6, 2)],
            # Round 7: Court 1: 1&10 vs 3&8 (11 v 11), Court 2: 2&9 vs 5&6 (11 v 11)
            [(0, 9, 2, 7, 1), (1, 8, 4, 5, 2)],
            # Round 8: Court 1: 3&10 vs 6&7 (13 v 13), Court 2: 5&8 vs 4&9 (13 v 13)
            [(2, 9, 5, 6, 1), (4, 7, 3, 8, 2)],
            # Round 9: Court 1: 1&8 vs 2&7 (9 v 9), Court 2: 3&6 vs 4&5 (9 v 9)
            [(0, 7, 1, 6, 1), (2, 5, 3, 4, 2)],
            # Round 10: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: 7&10 vs 8&9 (17 v 17)
            [(0, 4, 1, 3, 1), (6, 9, 7, 8, 2)],
            # Round 11: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 6&10 vs 7&9 (16 v 16)
            [(0, 3, 1, 2, 1), (5, 9, 6, 8, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 11-player Monarch of the Court
class MonarchOfTheCourt11(MoCTournamentArchetype):
    name = "11-player Monarch of the Court"
    description = "MoC: 11-player specific schedule with 2 courts."

    def calculate_rounds(self, num_players):
        if num_players != 11:
            raise ValueError("This tournament type requires exactly 11 players")
        return 14

    def calculate_courts(self, num_players):
        return 2

    def get_automatic_wins(self, num_players):
        """
        In 11-player MoC, seeds 1 & 2 play one fewer match than others.
        They each receive 1 automatic win to balance the standings.
        """
        return {0: 1, 1: 1}  # Seeds 1 & 2 (0-indexed) get +1 automatic win
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 11:
            raise ValueError("This tournament type requires exactly 11 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 11-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 1&3 vs 9&11 (4 v 20), Court 2: X
            [(0, 2, 8, 10, 1)],
            # Round 2: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2)],
            # Round 3: Court 1: 8&11 vs 9&10 (19 v 19), Court 2: 1&7 vs 2&5 (8 v 7)
            [(7, 10, 8, 9, 1), (0, 6, 1, 4, 2)],
            # Round 4: Court 1: 7&11 vs 8&10 (18 v 18), Court 2: 1&6 vs 3&4 (7 v 7)
            [(6, 10, 7, 9, 1), (0, 5, 2, 3, 2)],
            # Round 5: Court 1: 4&9 vs 10&11 (13 v 21), Court 2: 2&6 vs 3&5 (8 v 8)
            [(3, 8, 9, 10, 1), (1, 5, 2, 4, 2)],
            # Round 6: Court 1: 7&10 vs 8&9 (17 v 17), Court 2: 1&5 vs 2&4 (6 v 6)
            [(6, 9, 7, 8, 1), (0, 4, 1, 3, 2)],
            # Round 7: Court 1: 3&9 vs 4&7 (12 v 11), Court 2: 5&11 vs 6&10 (16 v 16)
            [(2, 8, 3, 6, 1), (4, 10, 5, 9, 2)],
            # Round 8: Court 1: 1&11 vs 4&8 (12 v 12), Court 2: 2&10 vs 5&7 (11 v 12)
            [(0, 10, 3, 7, 1), (1, 9, 4, 6, 2)],
            # Round 9: Court 1: 3&11 vs 4&10 (14 v 14), Court 2: 5&9 vs 6&8 (14 v 14)
            [(2, 10, 3, 9, 1), (4, 8, 5, 7, 2)],
            # Round 10: Court 1: 1&9 vs 3&7 (10 v 10), Court 2: 2&8 vs 4&6 (10 v 10)
            [(0, 8, 2, 6, 1), (1, 7, 3, 5, 2)],
            # Round 11: Court 1: 2&11 vs 6&7 (13 v 13), Court 2: 3&10 vs 5&8 (13 v 13)
            [(1, 10, 5, 6, 1), (2, 9, 4, 7, 2)],
            # Round 12: Court 1: 1&10 vs 5&6 (11 v 11), Court 2: 2&9 vs 3&8 (11 v 11)
            [(0, 9, 4, 5, 1), (1, 8, 2, 7, 2)],
            # Round 13: Court 1: 4&11 vs 6&9 (15 v 15), Court 2: 5&10 vs 7&8 (15 v 15)
            [(3, 10, 5, 8, 1), (4, 9, 6, 7, 2)],
            # Round 14: Court 1: 6&11 vs 7&9 (17 v 16), Court 2: 1&4 vs 2&3 (5 v 5)
            [(5, 10, 6, 8, 1), (0, 3, 1, 2, 2)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 12-player Monarch of the Court
class MonarchOfTheCourt12(MoCTournamentArchetype):
    name = "12-player Monarch of the Court"
    description = "MoC: 12-player specific schedule with 3 courts."
    
    def calculate_rounds(self, num_players):
        if num_players != 12:
            raise ValueError("This tournament type requires exactly 12 players")
        return 12
    
    def calculate_courts(self, num_players):
        return 3
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 12:
            raise ValueError("This tournament type requires exactly 12 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 12-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 2&6 vs 3&5 (8 v 8), Court 2: X, Court 3: 9&11 vs 8&12 (20 v 20)
            [(1, 5, 2, 4, 1), (8, 10, 7, 11, 3)],
            # Round 2: Court 1: 1&2 vs 5&10 (3 v 15), Court 2: 3&12 vs 7&8 (15 v 15), Court 3: 6&9 vs 4&11 (15 v 15)
            [(0, 1, 4, 9, 1), (2, 11, 6, 7, 2), (5, 8, 3, 10, 3)],
            # Round 3: Court 1: 1&6 vs 2&5 (7 v 7), Court 2: 3&4 vs 8&11 (7 v 19), Court 3: 7&12 vs 9&10 (19 v 19)
            [(0, 5, 1, 4, 1), (2, 3, 7, 10, 2), (6, 11, 8, 9, 3)],
            # Round 4: Court 1: 1&11 vs 4&8 (12 v 12), Court 2: 2&10 vs 6&12 (12 v 18), Court 3: 3&9 vs 5&7 (12 v 12)
            [(0, 10, 3, 7, 1), (1, 9, 5, 11, 2), (2, 8, 4, 6, 3)],
            # Round 5: Court 1: 1&9 vs 4&6 (10 v 10), Court 2: 2&8 vs 3&7 (10 v 10), Court 3: 5&11 vs 10&12 (16 v 22)
            [(0, 8, 3, 5, 1), (1, 7, 2, 6, 2), (4, 10, 9, 11, 3)],
            # Round 6: Court 1: 1&7 vs 3&11 (8 v 14), Court 2: 2&12 vs 5&9 (14 v 14), Court 3: 4&10 vs 6&8 (14 v 14)
            [(0, 6, 2, 10, 1), (1, 11, 4, 8, 2), (3, 9, 5, 7, 3)],
            # Round 7: Court 1: 1&3 vs 7&9 (4 v 16), Court 2: X, Court 3: 4&12 vs 6&10 (16 v 16)
            [(0, 2, 6, 8, 1), (3, 11, 5, 9, 3)],
            # Round 8: Court 1: 1&10 vs 3&8 (11 v 11), Court 2: 11&12 vs 5&6 (23 v 11), Court 3: 2&9 vs 4&7 (11 v 11)
            [(0, 9, 2, 7, 1), (10, 11, 4, 5, 2), (1, 8, 3, 6, 3)],
            # Round 9: Court 1: 1&12 vs 6&7 (13 v 13), Court 2: 2&11 vs 3&10 (13 v 13), Court 3: 5&8 vs 4&9 (13 v 13)
            [(0, 11, 5, 6, 1), (1, 10, 2, 9, 2), (4, 7, 3, 8, 3)],
            # Round 10: Court 1: 1&8 vs 2&7 (9 v 9), Court 2: 4&5 vs 3&6 (9 v 9), Court 3: 9&12 vs 10&11 (21 v 21)
            [(0, 7, 1, 6, 1), (3, 4, 2, 5, 2), (8, 11, 9, 10, 3)],
            # Round 11: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 5&12 vs 8&9 (17 v 17), Court 3: 7&10 vs 6&11 (17 v 17)
            [(0, 3, 1, 2, 1), (4, 11, 7, 8, 2), (6, 9, 5, 10, 3)],
            # Round 12: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: X, Court 3: 7&11 vs 8&10 (18 v 18)
            [(0, 4, 1, 3, 1), (6, 10, 7, 9, 3)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 13-player Monarch of the Court
class MonarchOfTheCourt13(MoCTournamentArchetype):
    name = "13-player Monarch of the Court"
    description = "MoC: 13-player specific schedule with 3 courts."
    
    def calculate_rounds(self, num_players):
        if num_players != 13:
            raise ValueError("This tournament type requires exactly 13 players")
        return 13
    
    def calculate_courts(self, num_players):
        return 3
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 13:
            raise ValueError("This tournament type requires exactly 13 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 13-player format
        schedule = [
            # Round 1: Court 1: 1&6 vs 2&5 (7 v 7), Court 2: 7&13 vs 9&11 (20 v 20), Court 3: 3&4 vs 8&12 (7 v 20)
            [(0, 5, 1, 4, 1), (6, 12, 8, 10, 2), (2, 3, 7, 11, 3)],
            # Round 2: Court 1: 1&7 vs 3&5 (8 v 8), Court 2: 8&13 vs 9&12 (21 v 21), Court 3: 2&6 vs 10&11 (8 v 21)
            [(0, 6, 2, 4, 1), (7, 12, 8, 11, 2), (1, 5, 9, 10, 3)],
            # Round 3: Court 1: 1&10 vs 4&7 (11 v 11), Court 2: 2&9 vs 3&8 (11 v 11), Court 3: 5&6 vs 11&13 (11 v 24)
            [(0, 9, 3, 6, 1), (1, 8, 2, 7, 2), (4, 5, 10, 12, 3)],
            # Round 4: Court 1: 1&11 vs 3&9 (12 v 12), Court 2: 2&10 vs 5&7 (12 v 12), Court 3: 4&8 vs 12&13 (12 v 25)
            [(0, 10, 2, 8, 1), (1, 9, 4, 6, 2), (3, 7, 11, 12, 3)],
            # Round 5: Court 1: 3&13 vs 5&11 (16 v 16), Court 2: 4&12 vs 7&9 (16 v 16), Court 3: 1&2 vs 6&10 (3 v 16)
            [(2, 12, 4, 10, 1), (3, 11, 6, 8, 2), (0, 1, 5, 9, 3)],
            # Round 6: Court 1: 4&13 vs 7&10 (17 v 17), Court 2: 5&12 vs 6&11 (17 v 17), Court 3: 1&3 vs 8&9 (4 v 17)
            [(3, 12, 6, 9, 1), (4, 11, 5, 10, 2), (0, 2, 7, 8, 3)],
            # Round 7: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9), Court 3: 9&13 vs 10&12 (22 v 22)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2), (8, 12, 9, 11, 3)],
            # Round 8: Court 1: 1&9 vs 3&7 (10 v 10), Court 2: 2&8 vs 4&6 (10 v 10), Court 3: 10&13 vs 11&12 (23 v 23)
            [(0, 8, 2, 6, 1), (1, 7, 3, 5, 2), (9, 12, 10, 11, 3)],
            # Round 9: Court 1: 1&12 vs 6&7 (13 v 13), Court 2: 2&11 vs 4&9 (13 v 13), Court 3: 3&10 vs 5&8 (13 v 13)
            [(0, 11, 5, 6, 1), (1, 10, 3, 8, 2), (2, 9, 4, 7, 3)],
            # Round 10: Court 1: 1&13 vs 2&12 (14 v 14), Court 2: 3&11 vs 6&8 (14 v 14), Court 3: 4&10 vs 5&9 (14 v 14)
            [(0, 12, 1, 11, 1), (2, 10, 5, 7, 2), (3, 9, 4, 8, 3)],
            # Round 11: Court 1: 2&13 vs 7&8 (15 v 15), Court 2: 3&12 vs 5&10 (15 v 15), Court 3: 4&11 vs 6&9 (15 v 15)
            [(1, 12, 6, 7, 1), (2, 11, 4, 9, 2), (3, 10, 5, 8, 3)],
            # Round 12: Court 1: 6&13 vs 9&10 (19 v 19), Court 2: 7&12 vs 8&11 (19 v 19), Court 3: 1&5 vs 2&4 (6 v 6)
            [(5, 12, 8, 9, 1), (6, 11, 7, 10, 2), (0, 4, 1, 3, 3)],
            # Round 13: Court 1: 5&13 vs 7&11 (18 v 18), Court 2: 6&12 vs 8&10 (18 v 18), Court 3: 1&4 vs 2&3 (5 v 5)
            [(4, 12, 6, 10, 1), (5, 11, 7, 9, 2), (0, 3, 1, 2, 3)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 14-player Monarch of the Court
class MonarchOfTheCourt14(MoCTournamentArchetype):
    name = "14-player Monarch of the Court"
    description = "MoC: 14-player specific schedule with 3 courts."

    def calculate_rounds(self, num_players):
        if num_players != 14:
            raise ValueError("This tournament type requires exactly 14 players")
        return 15

    def calculate_courts(self, num_players):
        return 3

    def get_automatic_wins(self, num_players):
        return {0: 1, 1: 1}
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 14:
            raise ValueError("This tournament type requires exactly 14 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 14-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 1&6 vs 2&5 (7 v 7), Court 2: 4&11 vs 8&14 (15 v 22), Court 3: 9&13 vs 10&12 (22 v 22)
            [(0, 5, 1, 4, 1), (3, 10, 7, 13, 2), (8, 12, 9, 11, 3)],
            # Round 2: Court 1: 1&7 vs 3&5 (8 v 8), Court 2: 9&14 vs 10&13 (23 v 23), Court 3: 2&6 vs 11&12 (8 v 23)
            [(0, 6, 2, 4, 1), (8, 13, 9, 12, 2), (1, 5, 10, 11, 3)],
            # Round 3: Court 1: 1&10 vs 3&8 (11 v 11), Court 2: 2&9 vs 4&7 (11 v 11), Court 3: 5&6 vs 12&14 (11 v 26)
            [(0, 9, 2, 7, 1), (1, 8, 3, 6, 2), (4, 5, 11, 13, 3)],
            # Round 4: Court 1: 1&11 vs 5&7 (12 v 12), Court 2: 2&10 vs 3&9 (12 v 12), Court 3: 4&8 vs 13&14 (12 v 27)
            [(0, 10, 4, 6, 1), (1, 9, 2, 8, 2), (3, 7, 12, 13, 3)],
            # Round 5: Court 1: 3&4 vs 6&13 (7 v 19), Court 2: 8&11 vs 5&14 (19 v 19), Court 3: 7&12 vs 9&10 (19 v 19)
            [(2, 3, 5, 12, 1), (7, 10, 4, 13, 2), (6, 11, 8, 9, 3)],
            # Round 6: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9), Court 3: 11&13 vs 10&14 (24 v 24)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2), (10, 12, 9, 13, 3)],
            # Round 7: Court 1: 1&9 vs 4&6 (10 v 10), Court 2: 2&8 vs 3&7 (10 v 10), Court 3: 12&13 vs 11&14 (25 v 25)
            [(0, 8, 3, 5, 1), (1, 7, 2, 6, 2), (11, 12, 10, 13, 3)],
            # Round 8: Court 1: 1&12 vs 6&7 (13 v 13), Court 2: 2&11 vs 3&10 (13 v 13), Court 3: 4&9 vs 5&8 (13 v 13)
            [(0, 11, 5, 6, 1), (1, 10, 2, 9, 2), (3, 8, 4, 7, 3)],
            # Round 9: Court 1: X, Court 2: X, Court 3: X
            # This round seems to be missing from the markdown
            # Round 10: Court 1: 1&13 vs 3&11 (14 v 14), Court 2: 2&12 vs 5&9 (14 v 14), Court 3: 4&10 vs 6&8 (14 v 14)
            [(0, 12, 2, 10, 1), (1, 11, 4, 8, 2), (3, 9, 5, 7, 3)],
            # Round 11: Court 1: 1&14 vs 6&9 (15 v 15), Court 2: 2&13 vs 7&8 (15 v 15), Court 3: 3&12 vs 5&10 (15 v 15)
            [(0, 13, 5, 8, 1), (1, 12, 6, 7, 2), (2, 11, 4, 9, 3)],
            # Round 12: Court 1: 1&3 vs 4&14 (4 v 18), Court 2: 5&13 vs 6&12 (18 v 18), Court 3: 7&11 vs 8&10 (18 v 18)
            [(0, 2, 3, 13, 1), (4, 12, 5, 11, 2), (6, 10, 7, 9, 3)],
            # Round 13: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: 7&14 vs 9&12 (21 v 21), Court 3: 8&13 vs 10&11 (21 v 21)
            [(0, 4, 1, 3, 1), (6, 13, 8, 11, 2), (7, 12, 9, 10, 3)],
            # Round 14: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 6&14 vs 9&11 (20 v 20), Court 3: 7&13 vs 8&12 (20 v 20)
            [(0, 3, 1, 2, 1), (5, 13, 8, 10, 2), (6, 12, 7, 11, 3)],
            # Round 15: Court 1: 2&14 vs 4&12 (16 v 16), Court 2: 3&13 vs 7&9 (16 v 16), Court 3: 5&11 vs 6&10 (16 v 16)
            [(1, 13, 3, 11, 1), (2, 12, 6, 8, 2), (4, 10, 5, 9, 3)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 15-player Monarch of the Court
class MonarchOfTheCourt15(MoCTournamentArchetype):
    name = "15-player Monarch of the Court"
    description = "MoC: 15-player specific schedule with 3 courts."

    def calculate_rounds(self, num_players):
        if num_players != 15:
            raise ValueError("This tournament type requires exactly 15 players")
        return 18

    def calculate_courts(self, num_players):
        return 3

    def get_automatic_wins(self, num_players):
        return {0: 1, 1: 1}
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 15:
            raise ValueError("This tournament type requires exactly 15 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 15-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 3&13 vs 8&9 (16 v 17), Court 2: X, Court 3: X
            [(2, 12, 7, 8, 1)],
            # Round 2: Court 1: 2&15 vs 4&13 (17 v 17), Court 2: 3&14 vs 6&11 (17 v 17), Court 3: 5&12 vs 7&10 (17 v 17)
            [(1, 14, 3, 12, 1), (2, 13, 5, 10, 2), (4, 11, 6, 9, 3)],
            # Round 3: Court 1: 1&6 vs 2&5 (7 v 7), Court 2: 7&8 vs 11&13 (15 v 24), Court 3: 9&15 vs 10&14 (24 v 24)
            [(0, 5, 1, 4, 1), (6, 7, 10, 12, 2), (8, 14, 9, 13, 3)],
            # Round 4: Court 1: 1&13 vs 6&8 (14 v 14), Court 2: 2&12 vs 3&11 (14 v 14), Court 3: 4&10 vs 5&9 (14 v 14)
            [(0, 12, 5, 7, 1), (1, 11, 2, 10, 2), (3, 9, 4, 8, 3)],
            # Round 5: Court 1: 1&7 vs 3&5 (8 v 8), Court 2: 11&14 vs 10&15 (25 v 25), Court 3: 2&6 vs 12&13 (8 v 25)
            [(0, 6, 2, 4, 1), (10, 13, 9, 14, 2), (1, 5, 11, 12, 3)],
            # Round 6: Court 1: 4&15 vs 7&12 (19 v 19), Court 2: 5&14 vs 9&10 (19 v 19), Court 3: 6&13 vs 8&11 (19 v 19)
            [(3, 14, 6, 11, 1), (4, 13, 8, 9, 2), (5, 12, 7, 10, 3)],
            # Round 7: Court 1: 1&11 vs 5&7 (12 v 12), Court 2: 2&10 vs 3&9 (12 v 12), Court 3: 4&8 vs 14&15 (12 v 29)
            [(0, 10, 4, 6, 1), (1, 9, 2, 8, 2), (3, 7, 13, 14, 3)],
            # Round 8: Court 1: 3&4 vs 6&15 (7 v 21), Court 2: 8&13 vs 7&14 (21 v 21), Court 3: 10&11 vs 9&12 (21 v 21)
            [(2, 3, 5, 14, 1), (7, 12, 6, 13, 2), (9, 10, 8, 11, 3)],
            # Round 9: Court 1: 1&12 vs 3&10 (13 v 13), Court 2: 2&11 vs 6&7 (13 v 13), Court 3: 4&9 vs 5&8 (13 v 13)
            [(0, 11, 2, 9, 1), (1, 10, 5, 6, 2), (3, 8, 4, 7, 3)],
            # Round 10: Court 1: 1&9 vs 4&6 (10 v 10), Court 2: 2&8 vs 3&7 (10 v 10), Court 3: 12&15 vs 13&14 (27 v 27)
            [(0, 8, 3, 5, 1), (1, 7, 2, 6, 2), (11, 14, 12, 13, 3)],
            # Round 11: Court 1: 3&15 vs 6&12 (18 v 18), Court 2: 4&14 vs 8&10 (18 v 18), Court 3: 5&13 vs 7&11 (18 v 18)
            [(2, 14, 5, 11, 1), (3, 13, 7, 9, 2), (4, 12, 6, 10, 3)],
            # Round 12: Court 1: 1&15 vs 7&9 (16 v 16), Court 2: 2&14 vs 5&11 (16 v 16), Court 3: 4&12 vs 6&10 (16 v 16)
            [(0, 14, 6, 8, 1), (1, 13, 4, 10, 2), (3, 11, 5, 9, 3)],
            # Round 13: Court 1: 1&3 vs 8&12 (4 v 20), Court 2: 7&13 vs 6&14 (20 v 20), Court 3: 5&15 vs 9&11 (20 v 20)
            [(0, 2, 7, 11, 1), (6, 12, 5, 13, 2), (4, 14, 8, 10, 3)],
            # Round 14: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: 8&15 vs 11&12 (23 v 23), Court 3: 9&14 vs 10&13 (23 v 23)
            [(0, 4, 1, 3, 1), (7, 14, 10, 11, 2), (8, 13, 9, 12, 3)],
            # Round 15: Court 1: 1&8 vs 2&7 (9 v 9), Court 2: 4&5 vs 3&6 (9 v 9), Court 3: 11&15 vs 12&14 (26 v 26)
            [(0, 7, 1, 6, 1), (3, 4, 2, 5, 2), (10, 14, 11, 13, 3)],
            # Round 16: Court 1: 1&10 vs 4&7 (11 v 11), Court 2: 2&9 vs 3&8 (11 v 11), Court 3: 5&6 vs 13&15 (11 v 28)
            [(0, 9, 3, 6, 1), (1, 8, 2, 7, 2), (4, 5, 12, 14, 3)],
            # Round 17: Court 1: 1&14 vs 6&9 (15 v 15), Court 2: 2&13 vs 5&10 (15 v 15), Court 3: 3&12 vs 4&11 (15 v 15)
            [(0, 13, 5, 8, 1), (1, 12, 4, 9, 2), (2, 11, 3, 10, 3)],
            # Round 18: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 8&14 vs 7&15 (22 v 22), Court 3: 9&13 vs 10&12 (22 v 22)
            [(0, 3, 1, 2, 1), (7, 13, 6, 14, 2), (8, 12, 9, 11, 3)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
                
# 16-player Monarch of the Court
class MonarchOfTheCourt16(MoCTournamentArchetype):
    name = "16-player Monarch of the Court"
    description = "MoC: 16-player specific schedule with 4 courts."
    
    def calculate_rounds(self, num_players):
        if num_players != 16:
            raise ValueError("This tournament type requires exactly 16 players")
        return 17
    
    def calculate_courts(self, num_players):
        return 4
    
    def generate_matchups(self, tournament_chart, players: List[Player], stage=None):
        if len(players) != 16:
            raise ValueError("This tournament type requires exactly 16 players")

        # Sort players by ranking
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)

        # Define schedule according to the 16-player format
        # Note: "X" in the markdown means no match on that court
        schedule = [
            # Round 1: Court 1: 1&11 vs 4&8 (12 v 12), Court 2: 5&7 vs 3&9 (12 v 12), Court 3: 13&15 vs 12&16 (28 v 28), Court 4: X
            [(0, 10, 3, 7, 1), (4, 6, 2, 8, 2), (12, 14, 11, 15, 3)],
            # Round 2: Court 1: 1&2 vs 6&13 (3 v 19), Court 2: 3&16 vs 9&10 (19 v 19), Court 3: 4&15 vs 7&12 (19 v 19), Court 4: 5&14 vs 8&11 (19 v 19)
            [(0, 1, 5, 12, 1), (2, 15, 8, 9, 2), (3, 14, 6, 11, 3), (4, 13, 7, 10, 4)],
            # Round 3: Court 1: 1&6 vs 2&5 (7 v 7), Court 2: 9&14 vs 8&15 (23 v 23), Court 3: 3&4 vs 11&12 (7 v 23), Court 4: 7&16 vs 10&13 (23 v 23)
            [(0, 5, 1, 4, 1), (8, 13, 7, 14, 2), (2, 3, 10, 11, 3), (6, 15, 9, 12, 4)],
            # Round 4: Court 1: 1&9 vs 7&11 (10 v 18), Court 2: 2&16 vs 6&12 (18 v 18), Court 3: 3&15 vs 8&10 (18 v 18), Court 4: 4&14 vs 5&13 (18 v 18)
            [(0, 8, 6, 10, 1), (1, 15, 5, 11, 2), (2, 14, 7, 9, 3), (3, 13, 4, 12, 4)],
            # Round 5: Court 1: 1&7 vs 3&5 (8 v 8), Court 2: 2&8 vs 9&15 (10 v 24), Court 3: 11&13 vs 10&14 (24 v 24), Court 4: X
            [(0, 6, 2, 4, 1), (1, 7, 8, 14, 2), (10, 12, 9, 13, 3)],
            # Round 6: Court 1: 1&15 vs 6&10 (16 v 16), Court 2: 2&14 vs 7&9 (16 v 16), Court 3: 3&13 vs 4&12 (16 v 16), Court 4: 5&11 vs 8&16 (16 v 24)
            [(0, 14, 5, 9, 1), (1, 13, 6, 8, 2), (2, 12, 3, 11, 3), (4, 10, 7, 15, 4)],
            # Round 7: Court 1: 1&13 vs 3&11 (14 v 14), Court 2: 2&12 vs 4&10 (14 v 14), Court 3: 6&8 vs 5&9 (14 v 14), Court 4: 7&15 vs 14&16 (22 v 30)
            [(0, 12, 2, 10, 1), (1, 11, 3, 9, 2), (5, 7, 4, 8, 3), (6, 14, 13, 15, 4)],
            # Round 8: Court 1: 1&3 vs 2&10 (4 v 12), Court 2: 4&16 vs 9&11 (20 v 20), Court 3: 5&15 vs 7&13 (20 v 20), Court 4: 6&14 vs 8&12 (20 v 20)
            [(0, 2, 1, 9, 1), (3, 15, 8, 10, 2), (4, 14, 6, 12, 3), (5, 13, 7, 11, 4)],
            # Round 9: Court 1: 2&6 vs 11&15 (8 v 26), Court 2: 10&16 vs 12&14 (26 v 26), Court 3: X, Court 4: X
            [(1, 5, 10, 14, 1), (9, 15, 11, 13, 2)],
            # Round 10: Court 1: 3&7 vs 4&6 (10 v 10), Court 2: X, Court 3: X, Court 4: X
            [(2, 6, 3, 5, 1)],
            # Round 11: Court 1: 1&14 vs 3&12 (15 v 15), Court 2: 2&13 vs 7&8 (15 v 15), Court 3: 6&9 vs 5&10 (15 v 15), Court 4: 4&11 vs 15&16 (15 v 31)
            [(0, 13, 2, 11, 1), (1, 12, 6, 7, 2), (5, 8, 4, 9, 3), (3, 10, 14, 15, 4)],
            # Round 12: Court 1: 1&16 vs 8&9 (17 v 17), Court 2: 2&15 vs 5&12 (17 v 17), Court 3: 3&14 vs 4&13 (17 v 17), Court 4: 6&11 vs 7&10 (17 v 17)
            [(0, 15, 7, 8, 1), (1, 14, 4, 11, 2), (2, 13, 3, 12, 3), (5, 10, 6, 9, 4)],
            # Round 13: Court 1: 1&8 vs 4&5 (9 v 9), Court 2: 2&7 vs 3&6 (9 v 9), Court 3: 9&16 vs 12&13 (25 v 25), Court 4: 10&15 vs 11&14 (25 v 25)
            [(0, 7, 3, 4, 1), (1, 6, 2, 5, 2), (8, 15, 11, 12, 3), (9, 14, 10, 13, 4)],
            # Round 14: Court 1: 1&5 vs 2&4 (6 v 6), Court 2: 8&14 vs 6&16 (22 v 22), Court 3: 9&13 vs 10&12 (22 v 22), Court 4: X
            [(0, 4, 1, 3, 1), (7, 13, 5, 15, 2), (8, 12, 9, 11, 3)],
            # Round 15: Court 1: 1&10 vs 4&7 (11 v 11), Court 2: 2&9 vs 3&8 (11 v 11), Court 3: 5&6 vs 13&14 (11 v 27), Court 4: 11&16 vs 12&15 (27 v 27)
            [(0, 9, 3, 6, 1), (1, 8, 2, 7, 2), (4, 5, 12, 13, 3), (10, 15, 11, 14, 4)],
            # Round 16: Court 1: 1&12 vs 6&7 (13 v 13), Court 2: 2&11 vs 4&9 (13 v 13), Court 3: 3&10 vs 5&8 (13 v 13), Court 4: 13&16 vs 14&15 (29 v 29)
            [(0, 11, 5, 6, 1), (1, 10, 3, 8, 2), (2, 9, 4, 7, 3), (12, 15, 13, 14, 4)],
            # Round 17: Court 1: 1&4 vs 2&3 (5 v 5), Court 2: 5&16 vs 7&14 (21 v 21), Court 3: 6&15 vs 8&13 (21 v 21), Court 4: 9&12 vs 10&11 (21 v 21)
            [(0, 3, 1, 2, 1), (4, 15, 6, 13, 2), (5, 14, 7, 12, 3), (8, 11, 9, 10, 4)],
        ]

        # Create matchups
        for round_idx, round_matches in enumerate(schedule, 1):
            for match in round_matches:
                p1, p2, p3, p4, court = match
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    stage=stage,
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
