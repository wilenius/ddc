from django.db import models
from .base_models import TournamentArchetype, Matchup, Pair
from typing import List, Dict, Optional, Any

# Function to map TournamentArchetype database objects to their code implementations
def get_implementation(archetype: TournamentArchetype) -> Optional[Any]:
    """
    Maps a TournamentArchetype database object to its code implementation.
    """
    # For now we use a simple name-based mapping
    implementations = {
        "Cade Loving's 8-player KoC": MonarchOfTheCourt8(),
        "4 pairs Swedish format": FourPairsSwedishFormat(),
        "8 pairs Swedish format": EightPairsSwedishFormat(),
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

    def generate_matchups(self, tournament_chart, pairs: List[Pair]):
        # Map pairs to seeds 1-based
        if len(pairs) != self.number_of_pairs:
            raise ValueError(f"This tournament format requires exactly {self.number_of_pairs} pairs")
        pairs_by_seed = {pair.seed: pair for pair in pairs}
        for round_idx, round_matches in enumerate(self.schedule, 1):
            for field_idx, (seed1, seed2) in enumerate(round_matches, 1):
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1=pairs_by_seed[seed1],
                    pair2=pairs_by_seed[seed2],
                    round_number=round_idx,
                    court_number=field_idx
                )

class FourPairsSwedishFormat(PairsTournamentArchetype):
    number_of_pairs = 4
    number_of_fields = 2
    schedule = [
        [(1, 3), (2, 4)],
        [(1, 4), (2, 3)],
        [(1, 2), (3, 4)],
    ]
    name = "4 pairs Swedish format"
    description = "Round robin: 3 rounds on 2 fields with 4 pairs."

class EightPairsSwedishFormat(PairsTournamentArchetype):
    number_of_pairs = 8
    number_of_fields = 4
    schedule = [
        [(1,5), (2,6), (3,7), (4,8)],
        [(1,6), (2,5), (3,8), (4,7)],
        [(1,7), (2,8), (3,5), (4,6)],
        [(1,8), (2,7), (3,6), (4,5)],
        [(1,3), (2,4), (5,7), (6,8)],
        [(1,4), (2,3), (5,8), (6,7)],
        [(1,2), (3,4), (5,6), (7,8)],
    ]
    name = "8 pairs Swedish format"
    description = "Round robin: 7 rounds on 4 fields with 8 pairs."

# -- Monarch of the Court base --
class MoCTournamentArchetype(TournamentArchetype):
    class Meta:
        abstract = True
    tournament_category = 'MOC'

# Existing Cade Loving's (now Monarch of the Court) format:
class MonarchOfTheCourt8(MoCTournamentArchetype):
    # Remove abstract=True to allow instantiation
    name = "Cade Loving's 8-player KoC"  # Exact match to migration
    description = "MoC: 8-player specific schedule."
    def calculate_rounds(self, num_players):
        if num_players != 8:
            raise ValueError("This tournament type requires exactly 8 players")
        return 7
    def calculate_courts(self, num_players):
        return 2
    # Use the base implementation's generate_matchups method instead of this incomplete one
    # The base implementation handles Cade Loving's 8-player tournament specifically
    # and is more complete than this implementation
