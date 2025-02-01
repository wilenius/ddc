from django.db import models
from .base_models import Matchup
from .auth import User

class MatchResultLog(models.Model):
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=[
        ('CREATE', 'Result Created'),
        ('UPDATE', 'Result Updated'),
        ('DELETE', 'Result Deleted'),
    ])
    details = models.JSONField()  # Store scores and other relevant details

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.get_action_display()} by {self.recorded_by} at {self.recorded_at}"