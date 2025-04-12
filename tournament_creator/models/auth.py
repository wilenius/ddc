from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom user model supporting roles: Admin, Player, Spectator.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        PLAYER = 'PLAYER', 'Player'
        SPECTATOR = 'SPECTATOR', 'Spectator'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.SPECTATOR,
    )

    def is_admin(self) -> bool:
        """Return True if the user is an admin."""
        return self.role == self.Role.ADMIN

    def is_player(self) -> bool:
        """Return True if the user is a player."""
        return self.role == self.Role.PLAYER

    def is_spectator(self) -> bool:
        """Return True if the user is a spectator."""
        return self.role == self.Role.SPECTATOR
