"""
Populate tournament matchups with simulated scores for testing.

Match outcomes are driven by ranking probabilities: the closer two teams'
ranking points, the closer the simulated match, with a real chance of upsets.

Examples:
    python manage.py simulate_scores 14
    python manage.py simulate_scores 14 --points 21 --sets 3      # cap defaults to 24
    python manage.py simulate_scores 14 --points 15 --cap 17
    python manage.py simulate_scores 14 --stage 1 --overwrite
    python manage.py simulate_scores 14 --stage 1 --clear
"""
import json
import math
import random
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from tournament_creator.models.base_models import TournamentChart, Matchup, Stage
from tournament_creator.models.logging import MatchResultLog
from tournament_creator.models.scoring import PairScore, PlayerScore
from tournament_creator.views.tournament_views import record_match_result

# Per-point win probability for the strongest possible mismatch in the
# tournament. 0.60 over a race to 15 gives the favourite roughly a 90% match
# win probability, so upsets still happen; evenly ranked teams sit near 0.50
# and produce close scores.
MAX_POINT_EDGE = 0.10
# Per-set "form of the day" jitter, so identical pairings don't always
# produce identical-looking scorelines.
FORM_JITTER = 0.03


class Command(BaseCommand):
    help = "Fill unscored matchups of a tournament with simulated, ranking-weighted results."

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int, help='TournamentChart id')
        parser.add_argument('--points', type=int, default=15,
                            help='Points a set is played to, win by 2 (default: 15)')
        parser.add_argument('--cap', type=int, default=None,
                            help='Hard point cap; first team to reach it wins the set '
                                 'regardless of margin (default: --points + 3)')
        parser.add_argument('--sets', type=int, default=None,
                            help='Best-of sets per match: the match stops once one team has won '
                                 'a majority, so --sets 3 plays a third set only on a 1-1 split '
                                 '(default: the tournament\'s default_sets_per_match)')
        parser.add_argument('--stage', type=int, default=None,
                            help='Only populate this stage number (default: all stages with matchups)')
        parser.add_argument('--overwrite', action='store_true',
                            help='Also re-simulate matchups that already have scores')
        parser.add_argument('--clear', action='store_true',
                            help='Delete scores from the selected matchups instead of simulating. '
                                 'For multi-phase formats this also resets the generated structure '
                                 '(matchups, pools) of the cleared stage and every stage after it, '
                                 'so the "Generate next phase" flow starts over.')
        parser.add_argument('--rng-seed', type=int, default=None,
                            help='Seed the random generator for reproducible results')

    def handle(self, *args, **options):
        try:
            tournament = TournamentChart.objects.get(id=options['tournament_id'])
        except TournamentChart.DoesNotExist:
            raise CommandError(f"Tournament {options['tournament_id']} does not exist")

        if options['rng_seed'] is not None:
            random.seed(options['rng_seed'])

        points = options['points']
        cap = options['cap'] if options['cap'] is not None else points + 3
        sets = options['sets'] or tournament.default_sets_per_match or 1
        if points < 1 or sets < 1:
            raise CommandError("--points and --sets must be positive")
        if cap < points:
            raise CommandError("--cap must be at least --points")

        matchups = Matchup.objects.filter(tournament_chart=tournament)
        stage = None
        if options['stage'] is not None:
            stage = Stage.objects.filter(tournament=tournament,
                                         stage_number=options['stage']).first()
            if not stage:
                raise CommandError(f"Tournament has no stage number {options['stage']}")
            matchups = matchups.filter(stage=stage)
        matchups = list(matchups.order_by('round_number', 'court_number', 'id'))

        user = get_user_model().objects.filter(is_superuser=True).first() \
            or get_user_model().objects.first()
        if not user:
            raise CommandError("No user exists to attribute the results to")

        if options['clear']:
            self._clear_scores(tournament, matchups, stage, user)
            return

        if not matchups:
            raise CommandError("No matchups found — has the tournament (or stage) been generated?")

        if not options['overwrite']:
            matchups = [m for m in matchups if not m.scores.exists()]
            if not matchups:
                self.stdout.write("All matchups already have scores; use --overwrite to re-simulate.")
                return

        spread = self._strength_spread(matchups)
        recorded = 0

        # Reuse the real scoring view so PairScore/PlayerScore aggregation and
        # the euros placement-match hook behave exactly as in production, but
        # keep test data from triggering notifications.
        with self._notifications_suppressed():
            for matchup in matchups:
                s1, s2 = self._team_strengths(matchup)
                # Best-of: stop as soon as one team has a majority of the sets
                sets_to_win = sets // 2 + 1
                team1_scores, team2_scores = [], []
                while len(team1_scores) < sets:
                    p1, p2 = self._simulate_set(s1, s2, spread, points, cap)
                    team1_scores.append(p1)
                    team2_scores.append(p2)
                    sets_won = sum(1 for a, b in zip(team1_scores, team2_scores) if a > b)
                    if max(sets_won, len(team1_scores) - sets_won) >= sets_to_win:
                        break

                self._record(tournament, matchup, team1_scores, team2_scores, user)
                recorded += 1
                self.stdout.write(
                    f"R{matchup.round_number} C{matchup.court_number}: "
                    f"{matchup.pair1 or ''} vs {matchup.pair2 or ''}  "
                    + "  ".join(f"{a}-{b}" for a, b in zip(team1_scores, team2_scores))
                )

        self.stdout.write(self.style.SUCCESS(
            f"Recorded {recorded} matchup(s) in tournament '{tournament.name}' "
            f"(to {points}, cap {cap}, {sets} set(s), as user '{user.username}')"
        ))

    def _clear_scores(self, tournament, matchups, stage, user):
        """Delete scores (and their log entries) from the given matchups."""
        scored = [m for m in matchups if m.scores.exists()]
        for m in scored:
            m.scores.all().delete()
        MatchResultLog.objects.filter(matchup__in=matchups).delete()

        # In multi-phase formats the later stages are generated from earlier
        # results, so clearing a stage also tears down the generated structure
        # (matchups, pools, manual tiebreak resolutions via cascade) of that
        # stage and every stage after it. Phase 1 is created with the
        # tournament and is kept.
        reset_stages = []
        from tournament_creator.models.tournament_types import get_implementation
        impl = get_implementation(tournament.archetype) if tournament.archetype else None
        if impl and getattr(impl, 'is_multi_phase', False):
            from_number = max(stage.stage_number, 2) if stage else 2
            for s in Stage.objects.filter(tournament=tournament,
                                          stage_number__gte=from_number).order_by('stage_number'):
                if s.matchups.exists() or s.pools.exists():
                    s.matchups.all().delete()
                    s.pools.all().delete()
                    reset_stages.append(s.name)

        # The aggregate standings are only recomputed when a result is
        # recorded, so deleting scores leaves them stale. Wipe them and
        # rebuild from whatever scored matchups remain (e.g. other stages
        # when clearing a single stage).
        PairScore.objects.filter(tournament=tournament).delete()
        PlayerScore.objects.filter(tournament=tournament).delete()

        remaining = [
            m for m in Matchup.objects.filter(tournament_chart=tournament)
            if m.scores.exists()
        ]
        with self._notifications_suppressed():
            for m in remaining:
                sets = list(m.scores.order_by('set_number'))
                self._record(tournament, m,
                             [s.team1_score for s in sets],
                             [s.team2_score for s in sets],
                             user)

        message = (f"Cleared scores from {len(scored)} matchup(s) in tournament "
                   f"'{tournament.name}'; standings rebuilt from {len(remaining)} "
                   f"still-scored matchup(s)")
        if reset_stages:
            message += f"; reset generated structure of: {', '.join(reset_stages)}"
        self.stdout.write(self.style.SUCCESS(message))

    def _notifications_suppressed(self):
        # Keep test data from triggering email/Signal notifications.
        return patch.multiple('tournament_creator.views.tournament_views',
                              send_email_notification=lambda **kw: None,
                              send_signal_notification=lambda **kw: None)

    def _record(self, tournament, matchup, team1_scores, team2_scores, user):
        """Record a result through the real scoring view."""
        request = RequestFactory().post(
            f'/tournament/{tournament.id}/matchup/{matchup.id}/record/',
            {'team1_scores': json.dumps(team1_scores),
             'team2_scores': json.dumps(team2_scores)},
        )
        request.user = user
        response = record_match_result(request, tournament.id, matchup.id)
        result = json.loads(response.content)
        if result.get('status') != 'success':
            raise CommandError(f"Failed to record matchup {matchup.id}: {result.get('message')}")

    def _team_strengths(self, matchup):
        """Ranking points of each side; works for pairs and MoC matchups."""
        if matchup.pair1_id and matchup.pair2_id:
            return matchup.pair1.ranking_points_sum, matchup.pair2.ranking_points_sum
        team1 = [matchup.pair1_player1, matchup.pair1_player2]
        team2 = [matchup.pair2_player1, matchup.pair2_player2]
        return (sum(p.ranking_points for p in team1 if p),
                sum(p.ranking_points for p in team2 if p))

    def _strength_spread(self, matchups):
        """Largest strength gap across the matchups, used to normalize edges."""
        diffs = [abs(a - b) for a, b in (self._team_strengths(m) for m in matchups)]
        return max(diffs) or 1.0

    def _simulate_set(self, strength1, strength2, spread, points, cap):
        """Play a set point by point: to `points`, win by 2, hard cap at `cap`."""
        edge = MAX_POINT_EDGE * math.tanh(2.0 * (strength1 - strength2) / spread)
        p_team1 = 0.5 + edge + random.uniform(-FORM_JITTER, FORM_JITTER)
        points1 = points2 = 0
        while True:
            if random.random() < p_team1:
                points1 += 1
            else:
                points2 += 1
            leader, trailer = max(points1, points2), min(points1, points2)
            if (leader >= points and leader - trailer >= 2) or leader >= cap:
                return points1, points2
