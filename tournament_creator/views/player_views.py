from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from ..models.base_models import Player
from ..views.auth import AdminRequiredMixin, SpectatorAccessMixin

class PlayerListView(SpectatorAccessMixin, ListView):
    """
    Displays a list of all players, ordered by ranking. Viewable by all logged-in users.
    """
    model = Player
    template_name = 'tournament_creator/player_list.html'
    context_object_name = 'players'
    ordering = ['ranking']

class PlayerCreateView(AdminRequiredMixin, CreateView):
    """
    Allows an admin to create a new player record.
    """
    model = Player
    template_name = 'tournament_creator/player_form.html'
    fields = ['first_name', 'last_name', 'ranking']
    success_url = reverse_lazy('player_list')

    def form_valid(self, response):
        messages.success(self.request, "Player created successfully!")
        return super().form_valid(response)

class PlayerUpdateView(AdminRequiredMixin, UpdateView):
    """
    Allows an admin to edit an existing player's details.
    """
    model = Player
    template_name = 'tournament_creator/player_form.html'
    fields = ['first_name', 'last_name', 'ranking']
    success_url = reverse_lazy('player_list')

    def form_valid(self, response):
        messages.success(self.request, "Player updated successfully!")
        return super().form_valid(response)

class PlayerDeleteView(AdminRequiredMixin, DeleteView):
    """
    Allows an admin to delete a player record.
    """
    model = Player
    template_name = 'tournament_creator/player_confirm_delete.html'
    success_url = reverse_lazy('player_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Player deleted successfully!")
        return super().delete(request, *args, **kwargs)
