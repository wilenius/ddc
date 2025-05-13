from django.views.generic import ListView, CreateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json
from ..models.base_models import TournamentChart, Matchup, TournamentArchetype, Player, Pair
from ..models.tournament_types import PairsTournamentArchetype
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog
from ..views.auth import SpectatorAccessMixin, PlayerOrAdminRequiredMixin
from ..forms import PairFormSet, MoCPlayerSelectForm

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
        archetype_id = self.request.GET.get('archetype') or self.request.POST.get('archetype')
        if archetype_id:
            archetype = TournamentArchetype.objects.get(id=archetype_id)
            context['archetype'] = archetype
            # Determine the tournament type (for only two allowed overall types)
            if hasattr(archetype, 'tournament_category') and archetype.tournament_category == 'MOC':
                context['moc_player_form'] = MoCPlayerSelectForm(self.request.POST or None)
            else:
                context['moc_player_form'] = None
        else:
            context['archetype'] = None
            context['moc_player_form'] = None
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        archetype_id = request.POST.get('archetype')
        archetype = TournamentArchetype.objects.get(id=archetype_id)
        # ----- PAIRS -----
        if archetype.tournament_category == 'PAIRS':
            # get number of pairs from archetype name, e.g. "2 pairs Swedish format"
            num_pairs = int(archetype.name.split()[0]) if archetype.name.split()[0].isdigit() else 2
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
                    number_of_rounds=num_pairs+1,  # fallback, update to your real logic
                    number_of_courts=min(num_pairs, 4), # fallback, update to your real logic
                )
                tournament.pairs.set(pairs)
                # pairs_archetype.generate_matchups(tournament, pairs)
                messages.success(request, "Tournament created successfully!")
                return redirect('tournament_detail', pk=tournament.pk)
            else:
                return render(request, 'tournament_creator/tournament_create_pairs.html', {
                    'archetype': archetype,
                    'pair_formset': pair_formset
                })
        # ----- MOC -----
        if hasattr(archetype, 'tournament_category') and archetype.tournament_category == 'MOC':
            moc_player_form = MoCPlayerSelectForm(request.POST)
            if moc_player_form.is_valid():
                players = moc_player_form.cleaned_data['players']
                tournament = self.get_form().save(commit=False)
                tournament.number_of_rounds = archetype.calculate_rounds(len(players))
                tournament.number_of_courts = archetype.calculate_courts(len(players))
                tournament.save()
                tournament.players.set(players)
                archetype.generate_matchups(tournament, players)
                messages.success(self.request, "Tournament created successfully!")
                return redirect('tournament_detail', pk=tournament.pk)
            else:
                context = self.get_context_data(object=None)
                context['archetype'] = archetype
                context['moc_player_form'] = moc_player_form
                return render(request, 'tournament_creator/tournament_create.html', context)
        # ----- GENERIC (should not happen for current archetypes, fallback) -----
        player_ids = self.request.POST.getlist('players')
        if not player_ids:
            messages.error(self.request, "Please select players for the tournament")
            context = self.get_context_data(object=None)
            context['archetype'] = archetype
            return render(request, self.template_name, context)
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
        self.object = None  # required for CreateView context
        archetype_id = request.GET.get('archetype')
        if archetype_id:
            archetype = TournamentArchetype.objects.get(id=archetype_id)
            if archetype.tournament_category == 'PAIRS':
                num_pairs = int(archetype.name.split()[0]) if archetype.name.split()[0].isdigit() else 2
                pair_formset = PairFormSet(prefix="pairs", initial=[{} for _ in range(num_pairs)])
                return render(request, 'tournament_creator/tournament_create_pairs.html', {
                    'archetype': archetype,
                    'pair_formset': pair_formset
                })
            if archetype.tournament_category == 'MOC':
                moc_player_form = MoCPlayerSelectForm()
                context = self.get_context_data()
                context['archetype'] = archetype
                context['moc_player_form'] = moc_player_form
                return render(request, 'tournament_creator/tournament_create.html', context)
        return super().get(request, *args, **kwargs)

class TournamentDetailView(SpectatorAccessMixin, DetailView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_detail.html'
    context_object_name = 'tournament'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tournament = self.get_object()
        context['matchups'] = Matchup.objects.filter(tournament_chart=tournament).order_by('round_number', 'court_number')
        
        # Get raw player scores - we'll sort with tiebreaks
        player_scores = list(PlayerScore.objects.filter(tournament=tournament))
        
        # Apply advanced tiebreak sorting
        context['player_scores'] = self.apply_tiebreaks(tournament, player_scores)
        
        context['match_logs'] = MatchResultLog.objects.filter(
            matchup__tournament_chart=tournament
        ).select_related('recorded_by', 'matchup').order_by('-recorded_at')[:10]
        context['can_record_scores'] = self.request.user.is_authenticated and (
            getattr(self.request.user, 'is_admin', lambda: False)()
            or getattr(self.request.user, 'is_player', lambda: False)()
        )
        
        # Get all players in the tournament for name disambiguation
        all_players = list(tournament.players.all())
        context['all_players'] = all_players
        
        # Enhance the matchups and player_scores with display_names
        for matchup in context['matchups']:
            if matchup.pair1_player1:
                matchup.pair1_player1.display_name = matchup.pair1_player1.get_display_name(all_players)
            if matchup.pair1_player2:
                matchup.pair1_player2.display_name = matchup.pair1_player2.get_display_name(all_players)
            if matchup.pair2_player1:
                matchup.pair2_player1.display_name = matchup.pair2_player1.get_display_name(all_players)
            if matchup.pair2_player2:
                matchup.pair2_player2.display_name = matchup.pair2_player2.get_display_name(all_players)
                
        for score in context['player_scores']:
            score.player.display_name = score.player.get_display_name(all_players)
            
        return context
        
    def apply_tiebreaks(self, tournament, player_scores):
        """
        Apply proper tiebreak analysis to sort players with equal wins.
        Tiebreak order:
        1. Overall wins
        2. Head-to-head record between tied players
        3. Point differential in games between tied players
        """
        # First sort by wins and total point differential (basic sort)
        sorted_scores = sorted(player_scores, key=lambda x: (-x.wins, -x.total_point_difference))
        
        # Look for groups of players with the same number of wins
        groups_of_tied_players = []
        current_group = []
        current_wins = None
        
        for score in sorted_scores:
            if current_wins is None or score.wins == current_wins:
                current_group.append(score)
                current_wins = score.wins
            else:
                if len(current_group) > 1:  # Only record groups with ties
                    groups_of_tied_players.append(list(current_group))
                current_group = [score]
                current_wins = score.wins
        
        # Add the last group if it has ties
        if len(current_group) > 1:
            groups_of_tied_players.append(list(current_group))
        
        # No ties, return the basic sort
        if not groups_of_tied_players:
            return sorted_scores
        
        # Process each group of tied players
        for group in groups_of_tied_players:
            # Get all matchups involving these players
            tied_player_ids = [score.player.id for score in group]
            
            # Create a record of head-to-head results
            h2h_results = {player_id: {'wins': 0, 'point_diff': 0} for player_id in tied_player_ids}
            
            # Find all matchups between tied players
            tied_matchups = Matchup.objects.filter(
                tournament_chart=tournament,
                scores__isnull=False
            ).filter(
                models.Q(pair1_player1__in=tied_player_ids) | 
                models.Q(pair1_player2__in=tied_player_ids) | 
                models.Q(pair2_player1__in=tied_player_ids) | 
                models.Q(pair2_player2__in=tied_player_ids)
            ).distinct()
            
            # Count head-to-head wins and point differentials
            for matchup in tied_matchups:
                # Check if this matchup is between tied players
                matchup_player_ids = set()
                if matchup.pair1_player1_id and matchup.pair1_player1_id in tied_player_ids:
                    matchup_player_ids.add(matchup.pair1_player1_id)
                if matchup.pair1_player2_id and matchup.pair1_player2_id in tied_player_ids:
                    matchup_player_ids.add(matchup.pair1_player2_id)
                if matchup.pair2_player1_id and matchup.pair2_player1_id in tied_player_ids:
                    matchup_player_ids.add(matchup.pair2_player1_id)
                if matchup.pair2_player2_id and matchup.pair2_player2_id in tied_player_ids:
                    matchup_player_ids.add(matchup.pair2_player2_id)
                
                # Skip if not all players are in the tied group
                if len(matchup_player_ids) < 2:
                    continue
                
                # Process all sets in this matchup
                for set_score in matchup.scores.all():
                    # Check each player's team and update their head-to-head results
                    for player_id in tied_player_ids:
                        team1 = player_id in (matchup.pair1_player1_id, matchup.pair1_player2_id)
                        team2 = player_id in (matchup.pair2_player1_id, matchup.pair2_player2_id)
                        
                        if team1 and set_score.winning_team == 1:
                            h2h_results[player_id]['wins'] += 1
                            h2h_results[player_id]['point_diff'] += set_score.point_difference
                        elif team2 and set_score.winning_team == 2:
                            h2h_results[player_id]['wins'] += 1
                            h2h_results[player_id]['point_diff'] += set_score.point_difference
                        elif team1 and set_score.winning_team == 2:
                            h2h_results[player_id]['point_diff'] -= set_score.point_difference
                        elif team2 and set_score.winning_team == 1:
                            h2h_results[player_id]['point_diff'] -= set_score.point_difference
            
            # Sort the tied players by their head-to-head results
            group.sort(key=lambda score: (
                -h2h_results[score.player.id]['wins'],  # Head-to-head wins
                -h2h_results[score.player.id]['point_diff']  # Head-to-head point differential
            ))
            
            # Store the tiebreak info for display
            for score in group:
                player_id = score.player.id
                score.h2h_wins = h2h_results[player_id]['wins']
                score.h2h_point_diff = h2h_results[player_id]['point_diff']
        
        # Rebuild the complete standings with tiebreak-sorted groups
        final_standings = []
        current_index = 0
        
        # Map of wins to groups of tied players
        tied_groups_by_wins = {
            group[0].wins: group for group in groups_of_tied_players
        }
        
        # Rebuild the sorted list with tiebreak groups
        for score in sorted_scores:
            if score.wins in tied_groups_by_wins and len(tied_groups_by_wins[score.wins]) > 0:
                # Add all players from this tied group
                tied_group = tied_groups_by_wins[score.wins]
                final_standings.extend(tied_group)
                tied_groups_by_wins[score.wins] = []  # Mark as processed
            elif score not in final_standings:
                # Add individual player not in a tie group
                final_standings.append(score)
        
        return final_standings

@login_required
@require_POST
def record_match_result(request, tournament_id, matchup_id):
    try:
        matchup = get_object_or_404(Matchup, id=matchup_id)
        tournament = get_object_or_404(TournamentChart, id=tournament_id)
        team1_scores = json.loads(request.POST.get('team1_scores', '[]'))
        team2_scores = json.loads(request.POST.get('team2_scores', '[]'))
        
        # Input validation
        if len(team1_scores) != len(team2_scores) or not team1_scores:
            return JsonResponse({'status': 'error', 'message': 'Invalid score data'})
        
        # Convert scores to integers
        team1_scores = [int(score) for score in team1_scores]
        team2_scores = [int(score) for score in team2_scores]
        
        # Calculate totals before we use them
        team1_total = sum(team1_scores)
        team2_total = sum(team2_scores)
        
        # Determine winning team based on number of sets won
        team1_sets_won = sum(1 for s1, s2 in zip(team1_scores, team2_scores) if s1 > s2)
        team2_sets_won = sum(1 for s1, s2 in zip(team1_scores, team2_scores) if s2 > s1)
        
        # Determine overall winner (team with most sets)
        if team1_sets_won > team2_sets_won:
            winning_team = 1
        elif team2_sets_won > team1_sets_won:
            winning_team = 2
        else:
            # In case of tie, use total points
            winning_team = 1 if team1_total > team2_total else 2
            
        # If teams have equal sets won and equal total points, use the first set winner as tiebreaker
        if team1_total == team2_total and team1_sets_won == team2_sets_won and team1_scores and team2_scores:
            winning_team = 1 if team1_scores[0] > team2_scores[0] else 2
        
        # Get all players involved in the matchup
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
        
        # Delete existing scores and create new ones
        matchup.scores.all().delete()
        for set_num, (s1, s2) in enumerate(zip(team1_scores, team2_scores), 1):
            # The winning_team and point_difference will be calculated automatically in the save method
            MatchScore.objects.create(
                matchup=matchup,
                set_number=set_num,
                team1_score=s1,
                team2_score=s2
            )
        
        # Create log entry
        MatchResultLog.objects.create(
            matchup=matchup,
            recorded_by=request.user,
            action='UPDATE',
            details={
                'team1_scores': team1_scores,
                'team2_scores': team2_scores,
                'winning_team': winning_team,
                'team1_sets_won': team1_sets_won,
                'team2_sets_won': team2_sets_won
            }
        )
        
        # Update player scores
        for player in players:
            player_score, _ = PlayerScore.objects.get_or_create(
                tournament=tournament,
                player=player
            )
            # Only count matchups that actually have scores recorded
            # We need to filter for matchups where this player participated AND have scores
            all_played = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
            ).annotate(
                has_scores=models.Count('scores')
            ).filter(
                has_scores__gt=0
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
        
    except Exception as e:
        # Log the error and return a helpful error message
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving match result: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Error saving score: {str(e)}'})
