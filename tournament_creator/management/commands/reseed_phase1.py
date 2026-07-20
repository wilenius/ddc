from django.db import transaction
from django.core.management.base import BaseCommand, CommandError

from tournament_creator.models import TournamentChart, Matchup
from tournament_creator.models.base_models import Pool
from tournament_creator.models.scoring import MatchScore
from tournament_creator.models.tournament_types import get_implementation


class Command(BaseCommand):
    help = (
        "Reseed a multi-phase pairs tournament's Phase 1 after a rankings refresh: "
        "recompute pair seeds from current player points, then regenerate the "
        "Phase 1 pools and matchups. Safe only while no scores are recorded and "
        "later phases have not been generated (see check_seeding first)."
    )

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int)
        parser.add_argument(
            '--yes', action='store_true',
            help="Skip the confirmation prompt and apply the reseed.",
        )

    def handle(self, *args, **options):
        tid = options['tournament_id']
        try:
            tournament = TournamentChart.objects.get(pk=tid)
        except TournamentChart.DoesNotExist:
            raise CommandError(f"Tournament {tid} does not exist")

        archetype_impl = get_implementation(tournament.archetype)
        if not getattr(archetype_impl, 'is_multi_phase', False):
            raise CommandError(
                f"Tournament '{tournament}' is not a multi-phase format; "
                "its Phase 1 is not regenerated from seeds this way."
            )

        pairs = list(tournament.pairs.select_related('player1', 'player2'))
        if not pairs:
            raise CommandError(f"Tournament '{tournament}' has no pairs")

        stages = list(tournament.stages.order_by('stage_number'))
        stage1 = stages[0]
        # Refuse to touch a tournament that is already underway.
        scored = MatchScore.objects.filter(matchup__tournament_chart=tournament).count()
        if scored:
            raise CommandError(
                f"{scored} match score(s) already recorded — refusing to regenerate. "
                "Clear scores first (simulate_scores --clear) if this is a test bed."
            )
        later_generated = any(s.matchups.exists() for s in stages[1:])
        if later_generated:
            raise CommandError(
                "A later phase has already been generated — this command only "
                "handles a fresh Phase 1. Regenerate from scratch instead."
            )

        # Compute the new seeding the same way tournament creation does: refresh
        # each pair's stored points, then order by points sum descending.
        for pair in pairs:
            pair.ranking_points_sum = pair.calculate_points_sum()
        reseeded = sorted(pairs, key=lambda p: p.ranking_points_sum, reverse=True)
        new_seed = {p.pk: idx for idx, p in enumerate(reseeded, start=1)}

        changed = [p for p in pairs if p.seed != new_seed[p.pk]]
        self.stdout.write(f"Tournament: {tournament.name} (id={tournament.pk})")
        if not changed:
            self.stdout.write(self.style.SUCCESS(
                "Seeding unchanged — nothing to regenerate."
            ))
            return
        self.stdout.write(f"{len(changed)} pair(s) change seed:")
        for pair in sorted(changed, key=lambda p: new_seed[p.pk]):
            self.stdout.write(
                f"  seed {pair.seed} -> {new_seed[pair.pk]}: {pair}"
            )

        if not options['yes']:
            answer = input("Apply reseed and regenerate Phase 1? [y/N] ").strip().lower()
            if answer not in ('y', 'yes'):
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            locked = TournamentChart.objects.select_for_update().get(pk=tournament.pk)
            # Re-check under lock that nothing was scored in the meantime.
            if MatchScore.objects.filter(matchup__tournament_chart=locked).exists():
                raise CommandError("Scores were recorded concurrently — aborting.")

            for pair in pairs:
                pair.seed = new_seed[pair.pk]
                pair.save()  # save() also recomputes ranking_points_sum

            Matchup.objects.filter(stage=stage1).delete()
            Pool.objects.filter(stage=stage1).delete()
            archetype_impl.generate_matchups(locked, pairs, stage=stage1)

        self.stdout.write(self.style.SUCCESS("Reseeded. New Phase 1 pools:"))
        for pool in stage1.pools.order_by('order'):
            members = ", ".join(
                str(pp.pair) for pp in pool.poolpair_set.order_by('position')
            )
            self.stdout.write(f"  {pool.name}: {members}")
