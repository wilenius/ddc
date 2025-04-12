from django.db import models
from .base_models import TournamentArchetype, Matchup
from typing import List, Dict

class KingOfTheCourt8Players(TournamentArchetype):
    """
    Implementation of Cade Loving's 8-player King of the Court tournament format.
    Requires exactly 8 players ranked 1-8, with predetermined matchups per round and court.
    """
    class Meta:
        proxy = True

    def calculate_rounds(self, num_players: int) -> int:
        """
        King of the Court always has 7 rounds for 8 players.
        Raises ValueError if the player count is not exactly 8.
        """
        if num_players != 8:
            raise ValueError("This tournament type requires exactly 8 players")
        return 7

    def calculate_courts(self, num_players: int) -> int:
        """
        King of the Court always uses 2 courts for its format.
        """
        return 2

    def generate_matchups(self, tournament_chart: models.Model, players: List[models.Model]) -> None:
        """
        Generates the matchups according to Cade Loving's published schedule.
        Players are matched by their ranking (1-8), not strictly arbitrary order.
        Raises ValueError on ranking/roster violation.
        """
        if len(players) != 8:
            raise ValueError("This tournament type requires exactly 8 players")
        # Create a lookup dictionary for players by ranking
        players_by_ranking: Dict[int, models.Model] = {player.ranking: player for player in players}
        if len(players_by_ranking) != 8 or not all(rank in players_by_ranking for rank in range(1, 9)):
            raise ValueError("Players must have unique rankings from 1 to 8")
        # Schedule tuples: (round, court, [team1_rank1, team1_rank2, team2_rank1, team2_rank2])
        schedule = [
            (1, 1, [1, 3, 6, 8]), (1, 2, [2, 4, 5, 7]),
            (2, 1, [1, 6, 4, 7]), (2, 2, [3, 8, 2, 5]),
            (3, 1, [1, 2, 7, 8]), (3, 2, [3, 4, 5, 6]),
            (4, 1, [1, 5, 2, 6]), (4, 2, [4, 8, 3, 7]),
            (5, 1, [1, 8, 4, 5]), (5, 2, [2, 7, 3, 6]),
            (6, 1, [1, 7, 3, 5]), (6, 2, [4, 6, 2, 8]),
            (7, 1, [1, 4, 2, 3]), (7, 2, [6, 7, 5, 8]),
        ]
        # Create each matchup for round & court
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
