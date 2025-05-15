from django.db import models
from django.utils import timezone
from django.conf import settings

class RankingsUpdate(models.Model):
    """Tracks when player rankings were last updated."""
    timestamp = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    division = models.CharField(max_length=10, default='O')
    player_count = models.IntegerField(default=0)
    successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Rankings Update"
        verbose_name_plural = "Rankings Updates"
    
    def __str__(self):
        return f"{self.division} Division - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"