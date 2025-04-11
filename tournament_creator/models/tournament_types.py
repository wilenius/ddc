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

        # Create a lookup dictionary for players by ranking
        players_by_ranking = {player.ranking: player for player in players}
        if len(players_by_ranking) != 8 or not all(rank in players_by_ranking for rank in range(1, 9)):
            raise ValueError("Players must have unique rankings from 1 to 8")
        
        # The schedule defines who plays whom in each round using player rankings (1-8)
        # Format: (round, court, [team1_rank1, team1_rank2, team2_rank1, team2_rank2])
        schedule = [
            # Round 1
            (1, 1, [1, 3, 6, 8]),      # 1&3 vs 6&8
            (1, 2, [2, 4, 5, 7]),      # 2&4 vs 5&7
            
            # Round 2
            (2, 1, [1, 6, 4, 7]),      # 1&6 vs 4&7
            (2, 2, [3, 8, 2, 5]),      # 3&8 vs 2&5
            
            # Round 3
            (3, 1, [1, 2, 7, 8]),      # 1&2 vs 7&8
            (3, 2, [3, 4, 5, 6]),      # 3&4 vs 5&6
            
            # Round 4
            (4, 1, [1, 5, 2, 6]),      # 1&5 vs 2&6
            (4, 2, [4, 8, 3, 7]),      # 4&8 vs 3&7
            
            # Round 5
            (5, 1, [1, 8, 4, 5]),      # 1&8 vs 4&5
            (5, 2, [2, 7, 3, 6]),      # 2&7 vs 3&6
            
            # Round 6
            (6, 1, [1, 7, 3, 5]),      # 1&7 vs 3&5
            (6, 2, [4, 6, 2, 8]),      # 4&6 vs 2&8
            
            # Round 7
            (7, 1, [1, 4, 2, 3]),      # 1&4 vs 2&3
            (7, 2, [6, 7, 5, 8]),      # 6&7 vs 5&8
        ]

        # Create matchups for each round and court
        for round_num, court_num, rankings in schedule:
            Matchup.objects.create(
                tournament_chart=tournament_chart,
                round_number=round_num,
                court_number=court_num,
                pair1_player1=players_by_ranking[rankings[0]],
                pair1_player2=players_by_ranking[rankings[1]],
                pair2_player1=players_by_ranking[rankings[2]],
                pair2_player2=players_by_ranking[rankings[3]]
            )