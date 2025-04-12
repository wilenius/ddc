from django.views.generic import ListView, CreateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models.base_models import TournamentChart, Matchup, TournamentArchetype, Player, Pair
from ..models.tournament_types import PairsTournamentArchetype
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog
from ..views.auth import SpectatorAccessMixin, PlayerOrAdminRequiredMixin
from ..forms import PairFormSet

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
        pairs_archetype = None
        try:
            pairs_archetype = archetype.get_real_instance()
        except AttributeError:
            pass
        is_pairs = isinstance(pairs_archetype, PairsTournamentArchetype)
        if is_pairs:
            num_pairs = pairs_archetype.number_of_pairs
            pair_formset = PairFormSet(request.POST, prefix="pairs", extra=num_pairs)
            if pair_formset.is_valid():
                seen_players = set()
                pairs = []
                for form in pair_formset:
                    p1 = form.cleaned_data['player1']
                    p2 = form.cleaned_data['player2']
                    if p1 == p2 or p1 in seen_players or p2 in seen_players:
                        pair_formset.non_form_errors = lambda: ['Each player must appear only once and every pair must be two different players!']
                        return render(request, 'tournament_creator/tournament_create_pairs.html', {
                            'archetype': archetype,
                            'pair_formset': pair_formset
                        })
                    seen_players.update([p1, p2])
                    pair = Pair.objects.create(player1=p1, player2=p2)
                    pairs.append(pair)
                tournament = TournamentChart.objects.create(
                    name=request.POST['name'],
                    date=request.POST['date'],
                    number_of_rounds=pairs_archetype.calculate_rounds(num_pairs),
                    number_of_courts=pairs_archetype.number_of_fields
                )
                tournament.pairs.set(pairs)
                pairs_archetype.generate_matchups(tournament, pairs)
                messages.success(request, "Tournament created successfully!")
                return redirect('tournament_detail', pk=tournament.pk)
            else:
                return render(request, 'tournament_creator/tournament_create_pairs.html', {
                    'archetype': archetype,
                    'pair_formset': pair_formset
                })
        player_ids = self.request.POST.getlist('players')
        if not player_ids:
            messages.error(self.request, "Please select players for the tournament")
            return self.form_invalid(self.get_form())
        players = list(Player.objects.filter(id__in=player_ids).order_by('ranking'))
        tournament = self.get_form().save(commit=False)
        tournament.number_of_rounds = archetype.calculate_rounds(len(players))
        tournament.number_of_courts = archetype.calculate_courts(len(players))
        tournament.save()
        tournament.players.set(players)
        archetype.generate_matchups(tournament, players)
        messages.success(self.request, "Tournament created successfully!")
        return redirect('tournament_detail', pk=tournament.pk)

    def get(self, request, *args, **kwargs):
        archetype_id = request.GET.get('archetype')
        if archetype_id:
            archetype = TournamentArchetype.objects.get(id=archetype_id)
            pairs_archetype = None
            try:
                pairs_archetype = archetype.get_real_instance()
            except AttributeError:
                pass
            is_pairs = isinstance(pairs_archetype, PairsTournamentArchetype)
            if is_pairs:
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
        context['can_record_scores'] = self.request.user.is_authenticated and (
            getattr(self.request.user, 'is_admin', lambda: False)()
            or getattr(self.request.user, 'is_player', lambda: False)()
        )
        return context

@login_required
@require_POST
def record_match_result(request, tournament_id, matchup_id):
    matchup = get_object_or_404(Matchup, id=matchup_id)
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    team1_scores = json.loads(request.POST.get('team1_scores', '[]'))
    team2_scores = json.loads(request.POST.get('team2_scores', '[]'))
    winning_team = int(request.POST.get('winning_team'))
    if len(team1_scores) != len(team2_scores) or not team1_scores:
        return JsonResponse({'status': 'error', 'message': 'Invalid score data'})
    if getattr(matchup, 'pair1', None) and getattr(matchup, 'pair2', None):
        players = [matchup.pair1.player1, matchup.pair1.player2, matchup.pair2.player1, matchup.pair2.player2]
    else:
        players = [
            getattr(matchup, 'pair1_player1', None),
            getattr(matchup, 'pair1_player2', None),
            getattr(matchup, 'pair2_player1', None),
            getattr(matchup, 'pair2_player2', None),
        ]
    players = [p for p in players if p]
    matchup.scores.all().delete()
    for set_num, (s1, s2) in enumerate(zip(team1_scores, team2_scores), 1):
        MatchScore.objects.create(
            matchup=matchup,
            set_number=set_num,
            team1_score=s1,
            team2_score=s2,
            winning_team=winning_team,
            point_difference=(s1 - s2 if winning_team == 1 else s2 - s1)
        )
    MatchResultLog.objects.create(
        matchup=matchup,
        recorded_by=request.user,
        action='UPDATE',
        details={
            'team1_scores': team1_scores,
            'team2_scores': team2_scores,
            'winning_team': winning_team,
        }
    )
    for player in players:
        player_score, _ = PlayerScore.objects.get_or_create(
            tournament=tournament,
            player=player
        )
        all_played = Matchup.objects.filter(
            tournament_chart=tournament
        ).filter(
            models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
            models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
        ).distinct()
        player_score.matches_played = all_played.count()
        player_score.wins = 0
        player_score.total_point_difference = 0
        for m in all_played:
            scores = list(m.scores.order_by('set_number'))
            if not scores:
                continue
            for s in scores:
                on_team1 = (player in [getattr(m, 'pair1_player1', None), getattr(m, 'pair1_player2', None)])
                on_team2 = (player in [getattr(m, 'pair2_player1', None), getattr(m, 'pair2_player2', None)])
                if on_team1 and s.winning_team == 1:
                    player_score.wins += 1
                    player_score.total_point_difference += s.point_difference
                elif on_team2 and s.winning_team == 2:
                    player_score.wins += 1
                    player_score.total_point_difference += s.point_difference
                elif on_team1 and s.winning_team == 2:
                    player_score.total_point_difference -= s.point_difference
                elif on_team2 and s.winning_team == 1:
                    player_score.total_point_difference -= s.point_difference
        player_score.save()
    return JsonResponse({'status': 'success'})
