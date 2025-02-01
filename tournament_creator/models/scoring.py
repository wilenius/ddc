from django.db import models
from .base_models import Player, Matchup, TournamentChart

class MatchScore(models.Model):
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE, related_name='scores')
    set_number = models.IntegerField()  # 1, 2, or 3
    team1_score = models.IntegerField()
    team2_score = models.IntegerField()
    winning_team = models.IntegerField(choices=[
        (1, 'Team 1'),
        (2, 'Team 2'),
    ])
    point_difference = models.IntegerField()  # Can be negative for losing team

    class Meta:
        unique_together = ['matchup', 'set_number']
        ordering = ['matchup', 'set_number']

    def __str__(self):
        return f"Set {self.set_number}: {self.team1_score}-{self.team2_score}"

    def save(self, *args, **kwargs):
        # Calculate point difference
        if self.winning_team == 1:
            self.point_difference = self.team1_score - self.team2_score
        else:
            self.point_difference = self.team2_score - self.team1_score
        super().save(*args, **kwargs)

class PlayerScore(models.Model):
    tournament = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    wins = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)  # Added field
    total_point_difference = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['tournament', 'player']
        ordering = ['-wins', '-total_point_difference']

    def __str__(self):
        return f"{self.player.first_name} - Wins: {self.wins}, Points: {self.total_point_difference}"