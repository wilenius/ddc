from django.core.management.base import BaseCommand
from tournament_creator.models import TournamentArchetype


class Command(BaseCommand):
    help = 'Populate default notes for tournament archetypes'

    def handle(self, *args, **options):
        archetype_notes = {
            "5-player Monarch of the Court": (
                "Three format options available (Simple, Double Your Fun, Full Permutation).\n"
                "Because Option A contains all the even-matchup possibilities, some pairings are repeated in Options B & C."
            ),
            "6-player Monarch of the Court": (
                "Two options: Option A has pair 4&6 eliminated (one game missing), Option B has pairs 1&3, 2&5, and 4&6 eliminated.\n"
                "The law of averages shows seeds #3 and #4 to be even, with seed #1 above seed #2, and seed #6 below seed #5.\n"
                "All seeds lose at least once in the full permutation of possible matchups."
            ),
            "7-player Monarch of the Court": (
                "One pair is eliminated to make the format come out evenly: pair 1&2.\n"
                "The analysis assigns them a free win (W*) to compensate."
            ),
            "8-player Monarch of the Court": (
                "Everyone plays against everyone else exactly twice, and with everyone else exactly once!\n\n"
                "Analysis: Pair 1&2's power is mitigated by matching them against pair 7&8 in round 3."
            ),
            "9-player Monarch of the Court": (
                "Check out the symmetry in the analysis!\n"
                "Rounds 1 and 10 contain only one game."
            ),
            "10-player Monarch of the Court": (
                "One pair is eliminated to make the format come out evenly: pair 1&2.\n"
                "The analysis assigns them a free win (W*) to compensate."
            ),
            "11-player Monarch of the Court": (
                "One pair is eliminated to make the format come out evenly: pair 1&2.\n"
                "The analysis assigns them a free win (W*) to compensate.\n\n"
                "Seeds 1 & 2 receive one automatic win each to balance the fact they play one fewer match than other players."
            ),
            "12-player Monarch of the Court": (
                "12-player format with 3 courts.\n"
                "Analysis shows good balance with seed #1 having net 3 wins down to seed #12 with net 3 losses."
            ),
            "13-player Monarch of the Court": (
                "Check out the great symmetry in the analysis!\n"
                "All players get excellent balance with seeds #1-4 each having net 2 wins, through to seeds #10-13 each having net 2 losses."
            ),
            "14-player Monarch of the Court": (
                "One pair is eliminated to make the format come out evenly: pair 1&2.\n"
                "The analysis assigns them a free win (W*) to compensate."
            ),
            "15-player Monarch of the Court": (
                "One pair, 1&2, is eliminated. The analysis assigns them a free win (W*).\n"
                "The first round contains only one match.\n\n"
                "Alternative: Can combine formats into pools (e.g., three 5-player formats, or one 7-player and one 8-player format)."
            ),
            "16-player Monarch of the Court": (
                "Each player gets to play against most of the other players—more than utilizing two pools where half advance, "
                "and with many more closely matched games.\n\n"
                "Round 10 serves as a break for most players; only 1 match is in play."
            ),
        }

        updated_count = 0
        for archetype_name, notes in archetype_notes.items():
            try:
                archetype = TournamentArchetype.objects.get(name=archetype_name)
                if not archetype.notes:  # Only update if notes are empty
                    archetype.notes = notes
                    archetype.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'Added notes for: {archetype_name}')
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Skipped (already has notes): {archetype_name}')
                    )
            except TournamentArchetype.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Archetype not found: {archetype_name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nUpdated {updated_count} archetype(s)')
        )
