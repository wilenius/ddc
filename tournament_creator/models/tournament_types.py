from django.db import models
from .base_models import TournamentArchetype, Matchup

class KingOfTheCourt8Players(TournamentArchetype):
    """
    Implementation of Cade Loving's 8-player King of the Court tournament format.
    """
    class Meta:
        proxy = True

    def calculate_rounds(self, num_players):
        """
        This tournament format has exactly 7 rounds
        """
        if num_players != 8:
            raise ValueError("This tournament type requires exactly 8 players")
        return 7

    def calculate_courts(self, num_players):
        """
        This tournament format uses exactly 2 courts
        """
        return 2

    def generate_matchups(self, tournament_chart, players):
        """
        Generates the matchups according to Cade Loving's schedule.
        Players are matched by their ranking (1-8).
        """
        if len(players) != 8:
            raise ValueError("This tournament type requires exactly 8 players")

        # Sort players by ranking
        players = list(players)
        players.sort(key=lambda x: x.ranking)
        
        # The schedule defines who plays whom in each round
        # Format: (round, court, [team1_idx1, team1_idx2, team2_idx1, team2_idx2])
        schedule = [
            # Round 1
            (1, 1, [0, 2, 5, 7]),      # 1&3 vs 6&8
            (1, 2, [1, 3, 4, 6]),      # 2&4 vs 5&7
            
            # Round 2
            (2, 1, [0, 5, 3, 6]),      # 1&6 vs 4&7
            (2, 2, [2, 7, 1, 4]),      # 3&8 vs 2&5
            
            # Round 3
            (3, 1, [0, 1, 6, 7]),      # 1&2 vs 7&8
            (3, 2, [2, 3, 4, 5]),      # 3&4 vs 5&6
            
            # Round 4
            (4, 1, [0, 4, 1, 5]),      # 1&5 vs 2&6
            (4, 2, [3, 7, 2, 6]),      # 4&8 vs 3&7
            
            # Round 5
            (5, 1, [0, 7, 3, 4]),      # 1&8 vs 4&5
            (5, 2, [1, 6, 2, 5]),      # 2&7 vs 3&6
            
            # Round 6
            (6, 1, [0, 6, 2, 4]),      # 1&7 vs 3&5
            (6, 2, [3, 5, 1, 7]),      # 4&6 vs 2&8
            
            # Round 7
            (7, 1, [0, 3, 1, 2]),      # 1&4 vs 2&3
            (7, 2, [5, 6, 4, 7]),      # 6&7 vs 5&8
        ]

        # Create matchups for each round and court
        for round_num, court_num, player_indices in schedule:
            Matchup.objects.create(
                tournament_chart=tournament_chart,
                round_number=round_num,
                court_number=court_num,
                pair1_player1=players[player_indices[0]],
                pair1_player2=players[player_indices[1]],
                pair2_player1=players[player_indices[2]],
                pair2_player2=players[player_indices[3]]
            )