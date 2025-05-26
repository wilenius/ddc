from django.db import models
from .logging import MatchResultLog

class NotificationBackendSetting(models.Model):
    BACKEND_CHOICES = [
        ('email', 'Email'),
        ('signal', 'Signal'),
        ('matrix', 'Matrix'),
    ]
    backend_name = models.CharField(max_length=50, choices=BACKEND_CHOICES, unique=True)
    is_active = models.BooleanField(default=False)
    config = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.backend_name

class NotificationLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    backend_setting = models.ForeignKey(NotificationBackendSetting, on_delete=models.CASCADE)
    success = models.BooleanField()
    details = models.TextField(blank=True)
    match_result_log = models.ForeignKey(
        MatchResultLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.timestamp} - Backend: {self.backend_setting.backend_name} - Success: {self.success}"
