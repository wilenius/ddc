from django.views.generic import ListView, CreateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from ..models.base_models import TournamentChart, TournamentArchetype, Player, Matchup
from ..models.tournament_types import MonarchOfTheCourt8
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog
from ..views.auth import AdminRequiredMixin, PlayerOrAdminRequiredMixin, SpectatorAccessMixin
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

    def form_valid(self, form):
        try:
            # Get selected players and archetype from POST data
            player_ids = self.request.POST.getlist('players')
            archetype_id = self.request.POST.get('archetype')
            
            if not player_ids:
                messages.error(self.request, "Please select players for the tournament")
                return self.form_invalid(form)
            
            # Get the archetype and players
            archetype = TournamentArchetype.objects.get(id=archetype_id)
            players = list(Player.objects.filter(id__in=player_ids).order_by('ranking'))
            
            # Create tournament without saving yet
            tournament = form.save(commit=False)
            tournament.number_of_rounds = archetype.calculate_rounds(len(players))
            tournament.number_of_courts = archetype.calculate_courts(len(players))
            tournament.save()
            
            # Add players to tournament
            tournament.players.set(players)

            # If it's the 8-player KoC format, use its specific logic
            if archetype.name == "Cade Loving's 8-player KoC":
                koc_format = MonarchOfTheCourt8.objects.get(id=archetype_id)
                koc_format.generate_matchups(tournament, players)
            else:
                # For other formats, use base archetype
                archetype.generate_matchups(tournament, players)
            
            messages.success(self.request, "Tournament created successfully!")
            return redirect('tournament_detail', pk=tournament.pk)
        
        except Exception as e:
            messages.error(self.request, f"Error creating tournament: {str(e)}")
            return self.form_invalid(form)

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
        ).select_related('recorded_by', 'matchup').order_by('-recorded_at')[:10]  # Show last 10 logs
        context['can_record_scores'] = self.request.user.is_admin() or self.request.user.is_player()
        return context

@login_required
def record_match_result(request, tournament_id, matchup_id):
    if request.method == 'POST':
        # Check permissions first
        if not (request.user.is_admin() or request.user.is_player()):
            return JsonResponse({
                'status': 'error',
                'message': 'Permission denied'
            }, status=403)
            
        matchup = get_object_or_404(Matchup, id=matchup_id)
        tournament = get_object_or_404(TournamentChart, id=tournament_id)
        
        # Get the score data from POST
        team1_scores = json.loads(request.POST.get('team1_scores'))
        team2_scores = json.loads(request.POST.get('team2_scores'))
        winning_team = request.POST.get('winning_team')
        
        if len(team1_scores) != len(team2_scores):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid score data'
            })
        
        # Get all players involved in this matchup
        all_players = [
            matchup.pair1_player1,
            matchup.pair1_player2,
            matchup.pair2_player1,
            matchup.pair2_player2
        ]
        
        # Store old scores for logging
        old_scores = None
        if matchup.scores.exists():
            old_scores = list(matchup.scores.values())
        
        # Reset scores for all players in this matchup
        for player in all_players:
            player_score, _ = PlayerScore.objects.get_or_create(
                tournament=tournament,
                player=player,
                defaults={'wins': 0, 'matches_played': 0, 'total_point_difference': 0}
            )
            # If editing, subtract this match from their totals
            if matchup.scores.exists():
                player_score.matches_played -= 1
                # Reset wins and point difference - we'll recalculate from all other matches
                player_score.wins = 0
                player_score.total_point_difference = 0
                player_score.save()
        
        # Delete existing scores for this matchup
        matchup.scores.all().delete()
        
        # Create new scores for each set
        total_point_diff = 0
        new_scores = []
        for set_num, (t1_score, t2_score) in enumerate(zip(team1_scores, team2_scores), 1):
            t1_score = int(t1_score)
            t2_score = int(t2_score)
            point_diff = t1_score - t2_score if winning_team == '1' else t2_score - t1_score
            total_point_diff += point_diff
            
            score = MatchScore.objects.create(
                matchup=matchup,
                set_number=set_num,
                team1_score=t1_score,
                team2_score=t2_score,
                winning_team=winning_team,
                point_difference=point_diff
            )
            new_scores.append(score)
        
        # Log the action
        MatchResultLog.objects.create(
            matchup=matchup,
            recorded_by=request.user,
            action='UPDATE' if old_scores else 'CREATE',
            details={
                'old_scores': old_scores,
                'new_scores': [
                    {
                        'set_number': s.set_number,
                        'team1_score': s.team1_score,
                        'team2_score': s.team2_score,
                        'winning_team': s.winning_team
                    } for s in new_scores
                ]
            }
        )
        
        # Recalculate scores for all players from all their matches
        for player in all_players:
            player_score = PlayerScore.objects.get(tournament=tournament, player=player)
            
            # Count all matches this player has been involved in
            matches_played = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) | 
                models.Q(pair1_player2=player) | 
                models.Q(pair2_player1=player) | 
                models.Q(pair2_player2=player)
            ).filter(
                scores__isnull=False
            ).distinct().count()
            
            player_score.matches_played = matches_played
            
            # Calculate wins and point difference from all matches
            for match in Matchup.objects.filter(tournament_chart=tournament, scores__isnull=False):
                match_scores = match.scores.all()
                if not match_scores.exists():
                    continue
                    
                first_score = match_scores.first()
                is_team1 = player in [match.pair1_player1, match.pair1_player2]
                is_team2 = player in [match.pair2_player1, match.pair2_player2]
                
                if is_team1 and first_score.winning_team == 1:
                    player_score.wins += 1
                    player_score.total_point_difference += match.scores.aggregate(
                        total=models.Sum('point_difference')
                    )['total']
                elif is_team2 and first_score.winning_team == 2:
                    player_score.wins += 1
                    player_score.total_point_difference += match.scores.aggregate(
                        total=models.Sum('point_difference')
                    )['total']
                elif is_team1 and first_score.winning_team == 2:
                    player_score.total_point_difference -= match.scores.aggregate(
                        total=models.Sum('point_difference')
                    )['total']
                elif is_team2 and first_score.winning_team == 1:
                    player_score.total_point_difference -= match.scores.aggregate(
                        total=models.Sum('point_difference')
                    )['total']
            
            player_score.save()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})