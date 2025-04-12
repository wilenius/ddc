from django.views.generic import ListView, CreateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from ..models.base_models import TournamentChart, TournamentArchetype, Player, Matchup, Pair
from ..models.tournament_types import MonarchOfTheCourt8, PairsTournamentArchetype
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog
from ..views.auth import AdminRequiredMixin, PlayerOrAdminRequiredMixin, SpectatorAccessMixin
from ..forms import PairFormSet
import json

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

    def post(self, request, *args, **kwargs):
        archetype_id = request.POST.get('archetype')
        archetype = TournamentArchetype.objects.get(id=archetype_id)
        # Check if this is a pairs tournament type
        if archetype.tournament_category == 'PAIRS':
            # Number of pairs for selected format
            pairs_archetype = archetype.get_real_instance()
            num_pairs = pairs_archetype.number_of_pairs
            pair_formset = PairFormSet(request.POST, prefix="pairs", extra=num_pairs)
            if pair_formset.is_valid():
                all_players = []
                for form in pair_formset:
                    p1 = form.cleaned_data['player1']
                    p2 = form.cleaned_data['player2']
                    all_players.extend([p1.pk, p2.pk])
                # Check uniqueness (no player in 2 pairs)
                if len(all_players) != len(set(all_players)):
                    pair_formset.non_form_errors = lambda: ['Each player must appear only once among all pairs!']
                    return render(request, 'tournament_creator/tournament_create_pairs.html', {
                        'archetype': archetype,
                        'pair_formset': pair_formset
                    })
                # Create the tournament
                tournament = TournamentChart.objects.create(
                    name=request.POST['name'],
                    date=request.POST['date'],
                    number_of_rounds=pairs_archetype.calculate_rounds(num_pairs),
                    number_of_courts=pairs_archetype.number_of_fields
                )
                pairs = []
                for form in pair_formset:
                    p1 = form.cleaned_data['player1']
                    p2 = form.cleaned_data['player2']
                    pair = Pair.objects.create(player1=p1, player2=p2)
                    pairs.append(pair)
                tournament.pairs.set(pairs)
                pairs_archetype.generate_matchups(tournament, pairs)
                messages.success(request, "Tournament created successfully!")
                return redirect('tournament_detail', pk=tournament.pk)
            else:
                return render(request, 'tournament_creator/tournament_create_pairs.html', {
                    'archetype': archetype,
                    'pair_formset': pair_formset
                })
        # Fallback to original (players) creation
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        archetype_id = request.GET.get('archetype')
        if archetype_id:
            archetype = TournamentArchetype.objects.get(id=archetype_id)
            if archetype.tournament_category == 'PAIRS':
                pairs_archetype = archetype.get_real_instance()
                num_pairs = pairs_archetype.number_of_pairs
                pair_formset = PairFormSet(prefix="pairs", initial=[{} for _ in range(num_pairs)])
                return render(request, 'tournament_creator/tournament_create_pairs.html', {
                    'archetype': archetype,
                    'pair_formset': pair_formset
                })
        return super().get(request, *args, **kwargs)

class TournamentDetailView(SpectatorAccessMixin, DetailView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_detail.html'
    context_object_name = 'tournament'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tournament = self.get_object()
        context['matchups'] = Matchup.objects.filter(tournament_chart=tournament).order_by('round_number', 'court_number')
        context['player_scores'] = PlayerScore.objects.filter(tournament=tournament).order_by('-wins', '-total_point_difference')
        context['match_logs'] = MatchResultLog.objects.filter(
            matchup__tournament_chart=tournament
        ).select_related('recorded_by', 'matchup').order_by('-recorded_at')[:10]
        context['can_record_scores'] = self.request.user.is_admin() or self.request.user.is_player()
        return context

# record_match_result and other classes unchanged ...
