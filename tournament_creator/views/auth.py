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
    Allows access to users who are either players or admins.
    """
    def test_func(self) -> bool:
        return self.request.user.is_admin() or self.request.user.is_player()

class SpectatorAccessMixin(LoginRequiredMixin):
    """
    Allows access to all logged-in users, typically for view-only data.
    """
    pass
