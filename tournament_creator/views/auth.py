from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows access only to admin users.
    """
    def test_func(self) -> bool:
        return self.request.user.is_admin()

class PlayerOrAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows access to users who may maintain the player list: players, tournament
    creators (their entrants may not be ranked yet) and admins.
    """
    def test_func(self) -> bool:
        return self.request.user.can_add_players()

class TournamentCreatorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Allows access to users who may create tournaments: global admins and users
    with the Tournament Creator role.
    """
    def test_func(self) -> bool:
        return self.request.user.can_create_tournaments()

class TournamentAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Object-level access: only directors of *this* tournament (its creator, the
    directors they appointed, and global admins) may proceed.

    The view must expose the tournament through ``get_object()``.
    """
    def test_func(self) -> bool:
        return self.get_object().user_can_administer(self.request.user)

class SpectatorAccessMixin(LoginRequiredMixin):
    """
    Allows access to all logged-in users, typically for view-only data.
    """
    pass
