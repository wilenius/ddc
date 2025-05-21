from django.db import models
from .base_models import TournamentArchetype, Matchup, Pair, Player
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
        "5-player Monarch of the Court": MonarchOfTheCourt5(),
        "6-player Monarch of the Court": MonarchOfTheCourt6(),
        "7-player Monarch of the Court": MonarchOfTheCourt7(),
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
    
    def generate_matchups(self, tournament_chart, players: List[Player]):
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
                    pair1_player1=sorted_players[p1],
                    pair1_player2=sorted_players[p2],
                    pair2_player1=sorted_players[p3],
                    pair2_player2=sorted_players[p4],
                    round_number=round_idx,
                    court_number=court
                )
