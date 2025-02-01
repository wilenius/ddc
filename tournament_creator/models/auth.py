from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        PLAYER = 'PLAYER', 'Player'
        SPECTATOR = 'SPECTATOR', 'Spectator'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.SPECTATOR,
    )

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_player(self):
        return self.role == self.Role.PLAYER

    def is_spectator(self):
        return self.role == self.Role.SPECTATOR