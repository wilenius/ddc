from django.db import models
from .base_models import Matchup
from .auth import User

class MatchResultLog(models.Model):
    """
    Stores log entries for match result actions (create, update, delete).
    Tracks who recorded the result and when, along with action-specific details.
    """
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(
        max_length=20,
        choices=[('CREATE', 'Result Created'),('UPDATE', 'Result Updated'),('DELETE', 'Result Deleted')],
    )
    details = models.JSONField()  # Store scores and any relevant metadata

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self) -> str:
        """
        String representation for admin/log review purposes.
        """
        return f"{self.get_action_display()} by {self.recorded_by} at {self.recorded_at}"
