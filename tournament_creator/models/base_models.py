from django.db import models
from typing import List

class Player(models.Model):
    """Represents a player registered in the system."""
    first_name: str = models.CharField(max_length=255)
    last_name: str = models.CharField(max_length=255)
    ranking: int = models.IntegerField()
    ranking_points: float = models.FloatField(default=0)

    def __str__(self) -> str:
        """Return the full name of the player."""
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['ranking']

class TournamentChart(models.Model):
    """Model storing tournament-level information, including players and structure."""
    name: str = models.CharField(max_length=255, default="Unnamed Tournament")
    date: models.DateField = models.DateField()
    players: models.ManyToManyField = models.ManyToManyField(Player, through='TournamentPlayer')
    number_of_rounds: int = models.IntegerField()
    number_of_courts: int = models.IntegerField()

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ['-date']

class TournamentPlayer(models.Model):
    """Link table for players in a specific tournament."""
    tournament_chart: TournamentChart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player: Player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        ordering = ['player__ranking']

class Matchup(models.Model):
    """A specific match between two pairs in a tournament round."""
    tournament_chart: TournamentChart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE, related_name='matchups')
    pair1_player1: Player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player1_matchups')
    pair1_player2: Player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player2_matchups')
    pair2_player1: Player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player1_matchups')
    pair2_player2: Player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player2_matchups')
    round_number: int = models.IntegerField()
    court_number: int = models.IntegerField()

    def __str__(self) -> str:
        return f"Round {self.round_number}, Court {self.court_number}"

    class Meta:
        ordering = ['round_number', 'court_number']

class TournamentArchetype(models.Model):
    """
    Abstract base for various tournament formats.
    Extend and override methods for custom formats.
    """
    name: str = models.CharField(max_length=255)
    description: str = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    def create_tournament(self, players: List[Player]) -> TournamentChart:
        tournament_chart = TournamentChart.objects.create(
            number_of_rounds=self.calculate_rounds(len(players)),
            number_of_courts=self.calculate_courts(len(players)),
        )
        tournament_chart.players.set(players)
        self.generate_matchups(tournament_chart, players)
        return tournament_chart

    def calculate_rounds(self, num_players: int) -> int:
        """Calculate the number of rounds based on the number of players."""
        return 6  # Default value

    def calculate_courts(self, num_players: int) -> int:
        """Calculate the number of courts based on players."""
        return 1  # Default value

    def generate_matchups(self, tournament_chart: TournamentChart, players: List[Player]) -> None:
        """To be implemented by subclasses: generate Matchup records."""
        pass
