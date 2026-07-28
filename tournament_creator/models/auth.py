from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom user model supporting roles: Admin, Player, Spectator.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        TOURNAMENT_CREATOR = 'TC', 'Tournament Creator'
        PLAYER = 'PLAYER', 'Player'
        SPECTATOR = 'SPECTATOR', 'Spectator'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.SPECTATOR,
    )

    @property
    def display_name(self) -> str:
        """Name of the linked ranking player, falling back to the username."""
        from django.core.exceptions import ObjectDoesNotExist
        try:
            player = self.player
        except (AttributeError, ObjectDoesNotExist):
            player = None
        return f"{player.first_name} {player.last_name}" if player else self.get_username()

    def is_admin(self) -> bool:
        """Return True if the user is an admin."""
        return self.role == self.Role.ADMIN

    def is_tournament_creator(self) -> bool:
        """Return True if the user may create tournaments of their own.

        Tournament creators get director rights on the tournaments they create
        (see ``TournamentChart.user_can_administer``), but no global rights.
        """
        return self.role == self.Role.TOURNAMENT_CREATOR

    def can_create_tournaments(self) -> bool:
        """Return True if the user is allowed to create new tournaments."""
        return self.is_admin() or self.is_tournament_creator()

    def can_add_players(self) -> bool:
        """Return True if the user may add players to the ranking list.

        Tournament creators need this for entrants who aren't ranked yet.
        """
        return self.is_admin() or self.is_tournament_creator() or self.is_player()

    def is_player(self) -> bool:
        """Return True if the user is a player."""
        return self.role == self.Role.PLAYER

    def is_spectator(self) -> bool:
        """Return True if the user is a spectator."""
        return self.role == self.Role.SPECTATOR
