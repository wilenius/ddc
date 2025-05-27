from django.views.generic import ListView, CreateView, DetailView, DeleteView
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
from ..views.auth import SpectatorAccessMixin, PlayerOrAdminRequiredMixin, AdminRequiredMixin
from ..forms import PairFormSet, MoCPlayerSelectForm
from ..notifications import send_email_notification, send_signal_notification

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
        # Custom sorting: category first, then by player count
        archetypes = list(TournamentArchetype.objects.all())
        archetypes.sort(key=lambda x: (x.tournament_category, x.player_count, x.name))
        context['archetypes'] = archetypes
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
        player_scores = self.apply_tiebreaks(tournament, player_scores)
        
        # Make sure all scores have tiebreak attributes (even if not in a tie)
        for score in player_scores:
            if not hasattr(score, 'h2h_wins'):
                score.h2h_wins = 0
                score.h2h_point_diff = 0
            if not hasattr(score, 'above_wins'):
                score.above_wins = 0
                score.above_pd = 0
                
        context['player_scores'] = player_scores
        
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
        4. Record against teams that placed above the initial set of tied teams
        5. Point differential in games against teams that placed above the initial set of tied teams
        6. Point differential in games against all teams in the pool
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
            
        # Get all matchups in this tournament with scores
        all_matchups = Matchup.objects.filter(
            tournament_chart=tournament,
            scores__isnull=False
        ).prefetch_related('scores').distinct()
        
        # Get players who placed above our tied groups (for tiebreak steps 4-5)
        above_player_ids = set()
        current_win_level = None
        for score in sorted_scores:
            if current_win_level is None:
                current_win_level = score.wins
            elif score.wins < current_win_level:
                # We've moved to a new, lower win level
                break
            
            # Add players at the current (highest) win level 
            above_player_ids.add(score.player.id)
        
        # Process each group of tied players
        for group in groups_of_tied_players:
            # Get all matchups involving these players
            tied_player_ids = [score.player.id for score in group]
            
            # Create a record structure to hold all tiebreak criteria
            tiebreak_records = {player_id: {
                'h2h_wins': 0,                 # Head-to-head wins (criterion 2)
                'h2h_point_diff': 0,           # Head-to-head point diff (criterion 3)
                'above_team_wins': 0,          # Wins against higher-placed teams (criterion 4)
                'above_team_point_diff': 0,    # Point diff against higher-placed teams (criterion 5)
                'total_point_diff': 0          # Point diff against all teams (criterion 6, already in score object)
            } for player_id in tied_player_ids}
            
            # Check each matchup to see if it applies to our tiebreak criteria
            for matchup in all_matchups:
                # Identify players in team 1 and team 2
                team1_players = set()
                team2_players = set()
                if matchup.pair1_player1_id: team1_players.add(matchup.pair1_player1_id)
                if matchup.pair1_player2_id: team1_players.add(matchup.pair1_player2_id)
                if matchup.pair2_player1_id: team2_players.add(matchup.pair2_player1_id)
                if matchup.pair2_player2_id: team2_players.add(matchup.pair2_player2_id)
                
                # Find tied players in this matchup
                tied_in_team1 = team1_players.intersection(tied_player_ids)
                tied_in_team2 = team2_players.intersection(tied_player_ids)
                
                # To count for head-to-head criteria, the match must involve players from the tied group
                # on both sides of the match (as opponents, not just as partners)
                is_h2h_match = len(tied_in_team1) > 0 and len(tied_in_team2) > 0
                
                # Identify players from higher-placed teams
                above_in_team1 = team1_players.intersection(above_player_ids)
                above_in_team2 = team2_players.intersection(above_player_ids)
                
                # Process all sets in this matchup
                for set_score in matchup.scores.all():
                    team1_won = set_score.winning_team == 1
                    
                    # Process each tied player's results
                    for player_id in tied_player_ids:
                        on_team1 = player_id in team1_players
                        on_team2 = player_id in team2_players
                        
                        if not (on_team1 or on_team2):
                            continue  # This player wasn't in this match
                        
                        # Calculate point differential from this player's perspective
                        pd = set_score.point_difference
                        if (on_team1 and not team1_won) or (on_team2 and team1_won):
                            pd = -pd  # This player's team lost, so negate the PD
                            
                        # Update head-to-head records (criterion 2-3)
                        if is_h2h_match:
                            if (on_team1 and team1_won) or (on_team2 and not team1_won):
                                tiebreak_records[player_id]['h2h_wins'] += 1
                            tiebreak_records[player_id]['h2h_point_diff'] += pd
                            
                        # Wins against higher-placed teams (criterion 4-5)
                        # If this player played against higher-placed teams, count it
                        opponent_has_above = False
                        if on_team1 and above_in_team2:
                            opponent_has_above = True
                        elif on_team2 and above_in_team1:
                            opponent_has_above = True
                            
                        if opponent_has_above:
                            if (on_team1 and team1_won) or (on_team2 and not team1_won):
                                tiebreak_records[player_id]['above_team_wins'] += 1
                            tiebreak_records[player_id]['above_team_point_diff'] += pd
            
            # Apply total point differential from all games
            for score in group:
                tiebreak_records[score.player.id]['total_point_diff'] = score.total_point_difference
            
            # Sort the tied players using all tiebreak criteria
            group.sort(key=lambda score: (
                -tiebreak_records[score.player.id]['h2h_wins'],           # Criterion 2: H2H wins
                -tiebreak_records[score.player.id]['h2h_point_diff'],     # Criterion 3: H2H point diff
                -tiebreak_records[score.player.id]['above_team_wins'],    # Criterion 4: Wins vs above teams
                -tiebreak_records[score.player.id]['above_team_point_diff'], # Criterion 5: PD vs above teams
                -tiebreak_records[score.player.id]['total_point_diff']    # Criterion 6: Total PD
            ))
            
            # Store the tiebreak info for display
            for score in group:
                player_id = score.player.id
                score.h2h_wins = tiebreak_records[player_id]['h2h_wins']
                score.h2h_point_diff = tiebreak_records[player_id]['h2h_point_diff']
                score.above_wins = tiebreak_records[player_id]['above_team_wins']
                score.above_pd = tiebreak_records[player_id]['above_team_point_diff']
        
        # Rebuild the complete standings with tiebreak-sorted groups
        final_standings = []
        
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

class TournamentDeleteView(AdminRequiredMixin, DeleteView):
    model = TournamentChart
    template_name = 'tournament_creator/tournamentchart_confirm_delete.html'
    success_url = reverse_lazy('tournament_list')
    
    def delete(self, request, *args, **kwargs):
        tournament = self.get_object()
        messages.success(request, f'Tournament "{tournament.name}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)

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
        match_log_entry = MatchResultLog.objects.create(
            matchup=matchup,
            recorded_by=request.user,
            action='UPDATE', # TODO: This should be dynamic (CREATE/UPDATE based on prior existence)
            details={
                'team1_scores': team1_scores,
                'team2_scores': team2_scores,
                'winning_team': winning_team,
                'team1_sets_won': team1_sets_won,
                'team2_sets_won': team2_sets_won
            }
        )
        
        # Send email notification
        try:
            send_email_notification(user_who_recorded=request.user, match_result_log_instance=match_log_entry)
        except Exception as e_notify:
            # Log notification error specifically, but don't let it break the main flow
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending email notification: {str(e_notify)}")
            # Optionally, add a message to the user or specific handling if notifications are critical
            # For now, just log and continue.

        # Send Signal notification
        try:
            send_signal_notification(user_who_recorded=request.user, match_result_log_instance=match_log_entry)
        except Exception as e_notify_signal:
            import logging # Ensure logger is available
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending Signal notification: {str(e_notify_signal)}")
            # Log and continue, similar to email.

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
