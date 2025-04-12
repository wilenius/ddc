from django.views.generic import ListView, CreateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models.base_models import TournamentChart, Matchup, Pair, TournamentArchetype, Player
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog
from ..views.auth import SpectatorAccessMixin, PlayerOrAdminRequiredMixin

class TournamentListView(SpectatorAccessMixin, ListView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_list.html'
    context_object_name = 'tournaments'

class TournamentCreateView(PlayerOrAdminRequiredMixin, CreateView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_create.html'
    fields = ['name', 'date']
    success_url = reverse_lazy('tournament_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['players'] = Player.objects.all().order_by('ranking')
        context['archetypes'] = TournamentArchetype.objects.all()
        return context

class TournamentDetailView(SpectatorAccessMixin, DetailView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_detail.html'
    context_object_name = 'tournament'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tournament = self.get_object()
        context['matchups'] = Matchup.objects.filter(tournament_chart=tournament).order_by('round_number', 'court_number')
        return context

# keep record_match_result and other logic as already defined ...
