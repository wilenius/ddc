from django.core.management.base import BaseCommand, CommandError
from tournament_creator.models import TournamentChart, Matchup
from tournament_creator.models.scoring import MatchScore


class Command(BaseCommand):
    help = (
        "Check whether a pairs tournament's stored seeding still matches the "
        "current player ranking points (e.g. after a rankings refresh)."
    )

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int)

    def handle(self, *args, **options):
        try:
            tournament = TournamentChart.objects.get(pk=options['tournament_id'])
        except TournamentChart.DoesNotExist:
            raise CommandError(f"Tournament {options['tournament_id']} does not exist")

        pairs = list(tournament.pairs.select_related('player1', 'player2'))
        if not pairs:
            raise CommandError(f"Tournament '{tournament}' has no pairs (not a pairs tournament?)")

        # Recompute what the seeding would be with current player points, using the
        # same ordering rule as tournament creation (points sum desc, stable on
        # entry order for ties).
        pairs.sort(key=lambda p: (p.entry_order is None, p.entry_order))
        reseeded = sorted(pairs, key=lambda p: p.calculate_points_sum(), reverse=True)
        new_seed_by_pair = {pair.pk: idx for idx, pair in enumerate(reseeded, start=1)}

        changes = []
        self.stdout.write(f"Tournament: {tournament.name} (id={tournament.pk})")
        self.stdout.write(f"{'seed':>4} {'new':>4}  {'stored pts':>10} {'fresh pts':>10}  pair")
        for pair in sorted(pairs, key=lambda p: (p.seed is None, p.seed)):
            fresh_sum = pair.calculate_points_sum()
            new_seed = new_seed_by_pair[pair.pk]
            marker = '' if new_seed == pair.seed else '  <-- CHANGED'
            self.stdout.write(
                f"{pair.seed!s:>4} {new_seed:>4}  {pair.ranking_points_sum:>10.2f} "
                f"{fresh_sum:>10.2f}  {pair}{marker}"
            )
            if new_seed != pair.seed:
                changes.append(pair)

        if not changes:
            self.stdout.write(self.style.SUCCESS(
                "Seeding unchanged: stored seeds match current ranking points."
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"Seeding WOULD change for {len(changes)} pair(s)."
        ))
        matchups = Matchup.objects.filter(tournament_chart=tournament)
        scored = MatchScore.objects.filter(matchup__in=matchups).count()
        self.stdout.write(self.style.WARNING(
            "Note: updating Pair.seed alone does NOT move pairs between pools — "
            "phase 1 matchups/pools are generated from seeds at creation time and "
            "would need to be regenerated."
        ))
        if scored:
            self.stdout.write(self.style.WARNING(
                f"{scored} match score(s) already recorded — clear test scores "
                "(simulate_scores --clear) before regenerating anything."
            ))
