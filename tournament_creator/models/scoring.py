from django.db import models
from .base_models import Player, Matchup, TournamentChart

class MatchScore(models.Model):
    """
    Stores the score for a single set within a matchup.
    Also keeps track of which team won, and point difference.
    """
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE, related_name='scores')
    set_number = models.IntegerField()  # 1, 2, or 3
    team1_score = models.IntegerField()
    team2_score = models.IntegerField()
    winning_team = models.IntegerField(choices=[(1, 'Team 1'), (2, 'Team 2')])
    point_difference = models.IntegerField()  # Can be negative for losing team

    class Meta:
        unique_together = ['matchup', 'set_number']
        ordering = ['matchup', 'set_number']

    def __str__(self) -> str:
        """
        Returns a string showing the set number and score.
        """
        return f"Set {self.set_number}: {self.team1_score}-{self.team2_score}"

    def save(self, *args, **kwargs) -> None:
        """
        Save method override to automatically set the winning_team and point_difference
        based on the current scores.
        """
        # Automatically determine winning team from scores
        if self.team1_score > self.team2_score:
            self.winning_team = 1
            self.point_difference = self.team1_score - self.team2_score
        elif self.team2_score > self.team1_score:
            self.winning_team = 2
            self.point_difference = self.team2_score - self.team1_score
        else:
            # In case of a tie (should be rare in DDC), default to team 1
            # This is just a fallback; ties should be handled at the UI level
            self.winning_team = 1
            self.point_difference = 0
        super().save(*args, **kwargs)

class PlayerScore(models.Model):
    """
    Aggregates a player's results in a tournament: total wins, matches played, and point difference.
    """
    tournament = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    wins = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)
    total_point_difference = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['tournament', 'player']
        ordering = ['-wins', '-total_point_difference']

    def __str__(self) -> str:
        """
        String summary of the player's score record for listing/ranking.
        """
        return f"{self.player.first_name} - Wins: {self.wins}, Points: {self.total_point_difference}"
