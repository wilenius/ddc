from django.views.generic import ListView, CreateView, DetailView, DeleteView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json
from ..models.base_models import TournamentChart, Matchup, TournamentArchetype, Player, Pair
from ..models.tournament_types import PairsTournamentArchetype
from ..models.scoring import MatchScore, PlayerScore, ManualTiebreakResolution
from ..models.logging import MatchResultLog
from ..models.notifications import NotificationBackendSetting # Added import
from ..views.auth import SpectatorAccessMixin, PlayerOrAdminRequiredMixin, AdminRequiredMixin
from ..forms import PairFormSet, MoCPlayerSelectForm, TournamentCreationForm # Added import
from ..notifications import send_email_notification, send_signal_notification

class TournamentListView(SpectatorAccessMixin, ListView):
    model = TournamentChart
    template_name = 'tournament_creator/tournament_list.html'
    context_object_name = 'tournaments'

class TournamentCreateView(PlayerOrAdminRequiredMixin, CreateView):
    model = TournamentChart
    form_class = TournamentCreationForm # Changed from fields
    template_name = 'tournament_creator/tournament_create.html'
    success_url = reverse_lazy('tournament_list')

    def get_initial(self):
        initial = super().get_initial()
        # Preserve name and date from GET parameters if available
        if 'name' in self.request.GET:
            initial['name'] = self.request.GET.get('name')
        if 'date' in self.request.GET:
            initial['date'] = self.request.GET.get('date')
        # Preserve tournament category
        if 'tournament_category' in self.request.GET:
            initial['tournament_category'] = self.request.GET.get('tournament_category')
        # Preserve name display format
        if 'name_display_format' in self.request.GET:
            initial['name_display_format'] = self.request.GET.get('name_display_format')
        # Preserve notification checkbox states from GET parameters if available
        if 'notify_by_email' in self.request.GET:
            initial['notify_by_email'] = self.request.GET.get('notify_by_email') == 'true'
        if 'notify_by_signal' in self.request.GET:
            initial['notify_by_signal'] = self.request.GET.get('notify_by_signal') == 'true'
        if 'notify_by_matrix' in self.request.GET:
            initial['notify_by_matrix'] = self.request.GET.get('notify_by_matrix') == 'true'
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['players'] = Player.objects.all().order_by('ranking')
        notification_settings = NotificationBackendSetting.objects.all()
        context['notification_backend_settings'] = {
            setting.backend_name: setting.is_active for setting in notification_settings
        }

        # Get tournament category from GET or POST
        tournament_category = self.request.GET.get('tournament_category') or self.request.POST.get('tournament_category')
        context['selected_category'] = tournament_category

        # Show player selection forms based on category
        if tournament_category == 'MOC':
            context['moc_player_form'] = MoCPlayerSelectForm(self.request.POST or None)
        elif tournament_category == 'PAIRS':
            # For pairs, we'll let the user select players and auto-detect pairs count
            context['moc_player_form'] = MoCPlayerSelectForm(self.request.POST or None)
        else:
            context['moc_player_form'] = None

        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        tournament_category = request.POST.get('tournament_category')

        # Auto-detect archetype based on player count and category
        form = self.get_form_class()(request.POST)
        moc_player_form = MoCPlayerSelectForm(request.POST)

        if not form.is_valid() or not moc_player_form.is_valid():
            context = self.get_context_data(object=None)
            context['form'] = form
            context['moc_player_form'] = moc_player_form
            return render(request, self.template_name, context)

        players = list(moc_player_form.cleaned_data['players'])
        num_players = len(players)

        # Find the matching archetype
        try:
            if tournament_category == 'MOC':
                archetype = TournamentArchetype.objects.get(
                    tournament_category='MOC',
                    name=f"{num_players}-player Monarch of the Court"
                )
            elif tournament_category == 'PAIRS':
                # For pairs, num_players should be even
                if num_players % 2 != 0:
                    messages.error(request, f"Pairs tournaments require an even number of players. You selected {num_players} players.")
                    context = self.get_context_data(object=None)
                    context['form'] = form
                    context['moc_player_form'] = moc_player_form
                    return render(request, self.template_name, context)

                num_pairs = num_players // 2
                archetype = TournamentArchetype.objects.get(
                    tournament_category='PAIRS',
                    name=f"{num_pairs} pairs doubles tournament"
                )
            else:
                messages.error(request, "Please select a tournament type")
                context = self.get_context_data(object=None)
                context['form'] = form
                return render(request, self.template_name, context)
        except TournamentArchetype.DoesNotExist:
            messages.error(request, f"No tournament format exists for {num_players} players in {tournament_category} category. Available sizes may vary.")
            context = self.get_context_data(object=None)
            context['form'] = form
            context['moc_player_form'] = moc_player_form
            return render(request, self.template_name, context)
        # Create tournament with auto-detected archetype
        if tournament_category == 'MOC':
            # MoC tournaments use individual players
            tournament = form.save(commit=False)
            tournament.archetype = archetype
            tournament.number_of_rounds = archetype.calculate_rounds(num_players)
            tournament.number_of_courts = archetype.calculate_courts(num_players)
            tournament.save()
            tournament.players.set(players)
            archetype.generate_matchups(tournament, players)
            messages.success(request, f"Tournament created successfully with {num_players} players!")
            return redirect('tournament_detail', pk=tournament.pk)

        elif tournament_category == 'PAIRS':
            # For pairs tournaments, create pairs from consecutive players (ranked)
            # Sort players by ranking
            sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)
            pairs = []
            for i in range(0, len(sorted_players), 2):
                pair = Pair.objects.create(
                    player1=sorted_players[i],
                    player2=sorted_players[i+1]
                )
                pairs.append(pair)

            tournament = form.save(commit=False)
            tournament.archetype = archetype
            from .models.tournament_types import get_implementation
            archetype_impl = get_implementation(archetype)
            tournament.number_of_rounds = archetype_impl.calculate_rounds(len(pairs))
            tournament.number_of_courts = archetype_impl.calculate_courts(len(pairs))
            tournament.save()
            tournament.pairs.set(pairs)
            archetype_impl.generate_matchups(tournament, pairs)
            messages.success(request, f"Tournament created successfully with {len(pairs)} pairs!")
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
        context['archetype'] = tournament.archetype  # Include archetype for notes access
        
        # Get raw player scores - we'll sort with tiebreaks
        player_scores = list(PlayerScore.objects.filter(tournament=tournament))
        
        # Apply advanced tiebreak sorting
        player_scores = self.apply_tiebreaks(tournament, player_scores)
        
        # Make sure all scores have tiebreak attributes (even if not in a tie)
        has_manual_resolution = False
        for idx, score in enumerate(player_scores, start=1):
            if not hasattr(score, 'h2h_wins'):
                score.h2h_wins = 0
                score.h2h_losses = 0
                score.h2h_point_diff = 0
            if not hasattr(score, 'above_wins'):
                score.above_wins = 0
                score.above_pd = 0
            # Add position number
            score.position = idx
            # Check if any score is manually resolved
            if hasattr(score, 'manually_resolved') and score.manually_resolved:
                has_manual_resolution = True

        context['player_scores'] = player_scores
        context['has_manual_resolution'] = has_manual_resolution

        # Check if tournament is complete (all matchups have scores)
        total_matchups = tournament.matchups.count()
        matchups_with_scores = tournament.matchups.filter(scores__isnull=False).distinct().count()
        context['tournament_complete'] = total_matchups > 0 and total_matchups == matchups_with_scores
        
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

        # Enhance the matchups and player_scores with display_names based on tournament preference
        use_last_names = tournament.name_display_format == 'LAST'

        for matchup in context['matchups']:
            if matchup.pair1_player1:
                matchup.pair1_player1.display_name = matchup.pair1_player1.get_display_name_last_name_mode(all_players) if use_last_names else matchup.pair1_player1.get_display_name(all_players)
            if matchup.pair1_player2:
                matchup.pair1_player2.display_name = matchup.pair1_player2.get_display_name_last_name_mode(all_players) if use_last_names else matchup.pair1_player2.get_display_name(all_players)
            if matchup.pair2_player1:
                matchup.pair2_player1.display_name = matchup.pair2_player1.get_display_name_last_name_mode(all_players) if use_last_names else matchup.pair2_player1.get_display_name(all_players)
            if matchup.pair2_player2:
                matchup.pair2_player2.display_name = matchup.pair2_player2.get_display_name_last_name_mode(all_players) if use_last_names else matchup.pair2_player2.get_display_name(all_players)

        for score in context['player_scores']:
            score.player.display_name = score.player.get_display_name_last_name_mode(all_players) if use_last_names else score.player.get_display_name(all_players)

        # Generate tournament structure if show_structure is enabled
        if tournament.show_structure:
            context['tournament_structure'] = self._generate_tournament_structure(tournament, all_players, use_last_names)

        return context
        
    def apply_tiebreaks(self, tournament, player_scores):
        """
        Apply proper tiebreak analysis to sort players with equal wins.
        
        For Monarch of the Court (MoC) tournaments:
        1. Overall wins
        2. Head-to-head W/L ratio against other tied players
        3. Point differential in games against other tied players
        4. Manual resolution (requires UI implementation)
        
        For other tournaments (Swedish pairs, etc.):
        1. Overall wins
        2. Head-to-head record between tied players
        3. Point differential in games between tied players
        4. Record against teams that placed above the initial set of tied teams
        5. Point differential in games against teams that placed above the initial set of tied teams
        6. Point differential in games against all teams in the pool
        """
        # Check if this is a MoC tournament by examining matchup structure
        is_moc_tournament = self._is_moc_tournament(tournament)
        
        if is_moc_tournament:
            return self._apply_moc_tiebreaks(tournament, player_scores)
        else:
            return self._apply_pairs_tiebreaks(tournament, player_scores)
    
    def _is_moc_tournament(self, tournament):
        """
        Determine if this is a MoC tournament by checking matchup structure.
        MoC tournaments use individual player fields, pairs tournaments use pair fields.
        """
        sample_matchup = tournament.matchups.first()
        if sample_matchup:
            # If it uses individual player fields, it's MoC
            return (sample_matchup.pair1_player1_id is not None or 
                    sample_matchup.pair1_player2_id is not None)
        return False
    
    def _apply_moc_tiebreaks(self, tournament, player_scores):
        """
        Apply MoC-specific tiebreak logic:
        1. Overall wins (already sorted)
        2. W/L ratio in games against other tied players
        3. Point differential in games against other tied players  
        4. Manual resolution (to be implemented)
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
        
        # Process each group of tied players
        for group in groups_of_tied_players:
            wins_level = group[0].wins
            tied_player_ids = [score.player.id for score in group]

            # Check if there's a manual resolution for this win level
            manual_resolution = None
            try:
                manual_resolution = ManualTiebreakResolution.objects.get(
                    tournament=tournament,
                    wins_tied_at=wins_level
                )
            except ManualTiebreakResolution.DoesNotExist:
                pass
            
            # Create a record structure to hold MoC tiebreak criteria
            tiebreak_records = {player_id: {
                'h2h_wins': 0,                 # Head-to-head wins against tied players
                'h2h_losses': 0,               # Head-to-head losses against tied players
                'h2h_point_diff': 0,           # Head-to-head point differential against tied players
                'needs_manual_resolution': False  # Flag for manual resolution
            } for player_id in tied_player_ids}
            
            # Check each matchup to see if it involves tied players
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
                
                # Only count games between tied players (head-to-head)
                is_h2h_match = len(tied_in_team1) > 0 and len(tied_in_team2) > 0
                
                if is_h2h_match:
                    # Process all sets in this matchup
                    for set_score in matchup.scores.all():
                        team1_won = set_score.winning_team == 1
                        
                        # Process each tied player's results against other tied players
                        for player_id in tied_player_ids:
                            on_team1 = player_id in team1_players
                            on_team2 = player_id in team2_players
                            
                            if not (on_team1 or on_team2):
                                continue  # This player wasn't in this match
                            
                            # Calculate point differential from this player's perspective
                            pd = set_score.point_difference
                            if (on_team1 and not team1_won) or (on_team2 and team1_won):
                                pd = -pd  # This player's team lost, so negate the PD
                                tiebreak_records[player_id]['h2h_losses'] += 1
                            else:
                                tiebreak_records[player_id]['h2h_wins'] += 1
                                
                            tiebreak_records[player_id]['h2h_point_diff'] += pd
            
            # Sort tied players using MoC tiebreak criteria
            def moc_sort_key(score):
                player_id = score.player.id
                h2h_wins = tiebreak_records[player_id]['h2h_wins']
                h2h_losses = tiebreak_records[player_id]['h2h_losses']
                
                # Calculate W/L ratio (avoid division by zero)
                if h2h_losses == 0:
                    h2h_ratio = float('inf') if h2h_wins > 0 else 0
                else:
                    h2h_ratio = h2h_wins / h2h_losses
                
                return (
                    -h2h_ratio,  # Higher W/L ratio is better
                    -tiebreak_records[player_id]['h2h_point_diff']  # Higher point diff is better
                )
            
            group.sort(key=moc_sort_key)

            # Store the tiebreak info for display
            for score in group:
                player_id = score.player.id
                score.h2h_wins = tiebreak_records[player_id]['h2h_wins']
                score.h2h_losses = tiebreak_records[player_id]['h2h_losses']
                score.h2h_point_diff = tiebreak_records[player_id]['h2h_point_diff']

                # Calculate ratio for display
                if score.h2h_losses == 0:
                    score.h2h_ratio = float('inf') if score.h2h_wins > 0 else 0
                else:
                    score.h2h_ratio = score.h2h_wins / score.h2h_losses

            # If manual resolution exists, apply it now (after tiebreak stats are calculated)
            if manual_resolution:
                # Get the automatic order before manual override
                auto_order = [score.player.id for score in group]

                # Apply manual order
                player_order = {player_id: idx for idx, player_id in enumerate(manual_resolution.resolved_order)}
                group.sort(key=lambda score: player_order.get(score.player.id, 999))

                # Get manual order after sorting
                manual_order = [score.player.id for score in group]

                # Mark as manually resolved only if order differs from automatic
                order_differs = auto_order != manual_order

                for score in group:
                    score.manually_resolved = order_differs
                    score.manual_resolution_reason = manual_resolution.reason if order_differs else None
        
        # Rebuild the complete standings with tiebreak-sorted groups
        return self._rebuild_standings(sorted_scores, groups_of_tied_players)
    
    def _apply_pairs_tiebreaks(self, tournament, player_scores):
        """
        Apply the existing 6-step tiebreak logic for pairs tournaments.
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
        return self._rebuild_standings(sorted_scores, groups_of_tied_players)
    
    def _rebuild_standings(self, sorted_scores, groups_of_tied_players):
        """
        Helper method to rebuild final standings with tiebreak-sorted groups.
        """
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

    def _generate_tournament_structure(self, tournament, all_players, use_last_names):
        """
        Generate tournament structure data for display.
        Returns a dict with court_numbers and rounds data.
        """
        # Get all matchups ordered by round and court
        matchups = tournament.matchups.all().order_by('round_number', 'court_number')

        if not matchups:
            return {'court_numbers': [], 'rounds': []}

        # Determine court numbers and round numbers
        court_numbers = sorted(set(m.court_number for m in matchups))
        round_numbers = sorted(set(m.round_number for m in matchups))

        # Create player seeding map (rank -> seed number)
        tournament_players = list(tournament.players.all().order_by('ranking'))
        seed_map = {player.id: idx + 1 for idx, player in enumerate(tournament_players)}

        # Build structure by rounds
        rounds_data = []
        for round_num in round_numbers:
            round_matchups = matchups.filter(round_number=round_num).order_by('court_number')

            # Create matchups for each court in this round
            matchup_strings = []
            for court_num in court_numbers:
                matchup = round_matchups.filter(court_number=court_num).first()

                if matchup:
                    matchup_str = self._format_matchup_structure(matchup, seed_map, all_players, use_last_names)
                    matchup_strings.append(matchup_str)
                else:
                    matchup_strings.append('-')

            rounds_data.append({
                'round_number': round_num,
                'matchups': matchup_strings
            })

        return {
            'court_numbers': court_numbers,
            'rounds': rounds_data
        }

    def _format_matchup_structure(self, matchup, seed_map, all_players, use_last_names):
        """
        Format a single matchup for structure display showing seed numbers.
        For MoC: "1&3 vs 6&8"
        For Pairs: "Pair1 vs Pair2"
        """
        # Check if this is MoC (individual players) or Pairs tournament
        if matchup.pair1_player1_id:
            # MoC tournament - show seed numbers
            p1_seed = seed_map.get(matchup.pair1_player1_id, '?')
            p2_seed = seed_map.get(matchup.pair1_player2_id, '?') if matchup.pair1_player2_id else None
            p3_seed = seed_map.get(matchup.pair2_player1_id, '?')
            p4_seed = seed_map.get(matchup.pair2_player2_id, '?') if matchup.pair2_player2_id else None

            if p2_seed and p4_seed:
                return f"{p1_seed}&{p2_seed} vs {p3_seed}&{p4_seed}"
            else:
                return f"{p1_seed} vs {p3_seed}"
        elif matchup.pair1_id:
            # Pairs tournament - show pair names or seeds
            pair1_name = str(matchup.pair1)
            pair2_name = str(matchup.pair2)
            return f"{pair1_name} vs {pair2_name}"
        else:
            return "-"

class TournamentDownloadResultsView(SpectatorAccessMixin, View):
    """Download tournament results as a text file."""

    def get(self, request, pk):
        tournament = get_object_or_404(TournamentChart, pk=pk)

        # Get all players for name display
        all_players = list(Player.objects.all())

        # Get player scores with tiebreaks applied
        player_scores = list(PlayerScore.objects.filter(tournament=tournament))

        # Get detail view instance to reuse tiebreak logic
        detail_view = TournamentDetailView()
        detail_view.apply_tiebreaks(tournament, player_scores)

        # Add position numbers
        for idx, score in enumerate(player_scores, start=1):
            score.position = idx

        # Build the text content
        lines = []
        lines.append(f"Tournament: {tournament.name}")
        lines.append(f"Date: {tournament.date.strftime('%B %d, %Y')}")
        lines.append("")
        lines.append("Final Standings:")
        lines.append("-" * 60)

        for score in player_scores:
            # Use full name (first + last)
            player = score.player
            full_name = f"{player.first_name} {player.last_name}".strip()
            if not full_name:
                full_name = player.username

            lines.append(f"{score.position}. {full_name} - {score.wins}W {score.total_point_difference:+d}PD")

        # Create response with text file
        response = HttpResponse('\n'.join(lines), content_type='text/plain')
        filename = f"{tournament.name.replace(' ', '_')}_{tournament.date.strftime('%Y%m%d')}.txt"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

class TournamentDeleteView(AdminRequiredMixin, DeleteView):
    model = TournamentChart
    template_name = 'tournament_creator/tournamentchart_confirm_delete.html'
    success_url = reverse_lazy('tournament_list')

    def delete(self, request, *args, **kwargs):
        tournament = self.get_object()
        messages.success(request, f'Tournament "{tournament.name}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)

@login_required
def manual_tiebreak_resolution(request, tournament_id):
    """
    View to manually resolve tiebreaks for tournament directors.
    Shows tied players and allows manual ordering.
    """
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    
    # Get player scores for this tournament
    player_scores = PlayerScore.objects.filter(tournament=tournament).order_by('-wins', '-total_point_difference')
    
    # Find groups of tied players
    ties = []
    current_group = []
    current_wins = None
    
    for score in player_scores:
        if current_wins is None or score.wins == current_wins:
            current_group.append(score)
            current_wins = score.wins
        else:
            if len(current_group) > 1:  # Only show groups with ties
                ties.append({
                    'wins': current_wins,
                    'players': current_group.copy(),
                    'resolved': ManualTiebreakResolution.objects.filter(
                        tournament=tournament, wins_tied_at=current_wins
                    ).exists()
                })
            current_group = [score]
            current_wins = score.wins
    
    # Add the last group if it has ties
    if len(current_group) > 1:
        ties.append({
            'wins': current_wins,
            'players': current_group.copy(),
            'resolved': ManualTiebreakResolution.objects.filter(
                tournament=tournament, wins_tied_at=current_wins
            ).exists()
        })
    
    if request.method == 'POST':
        wins_level = int(request.POST.get('wins_level'))
        player_order = request.POST.getlist('player_order')  # List of player IDs in order
        reason = request.POST.get('reason', '')
        
        # Delete existing resolution if any
        ManualTiebreakResolution.objects.filter(
            tournament=tournament, wins_tied_at=wins_level
        ).delete()
        
        # Create new resolution
        resolution = ManualTiebreakResolution.objects.create(
            tournament=tournament,
            wins_tied_at=wins_level,
            resolved_order=[int(pid) for pid in player_order],
            reason=reason,
            resolved_by=request.user
        )
        
        # Add tied players to the many-to-many field
        tied_player_ids = [int(pid) for pid in player_order]
        resolution.tied_players.set(Player.objects.filter(id__in=tied_player_ids))
        
        messages.success(request, f'Manual tiebreak resolution saved for players with {wins_level} wins.')
        return redirect('tournament_detail', pk=tournament_id)
    
    return render(request, 'tournament_creator/manual_tiebreak_resolution.html', {
        'tournament': tournament,
        'ties': ties
    })

def _is_moc_tournament_helper(tournament):
    """
    Helper function to determine if a tournament is MoC format.
    MoC tournaments use individual player fields, pairs tournaments use pair fields.
    """
    sample_matchup = tournament.matchups.first()
    if sample_matchup:
        # If it uses individual player fields, it's MoC
        return (sample_matchup.pair1_player1_id is not None or
                sample_matchup.pair1_player2_id is not None)
    return False

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
            send_email_notification(
                user_who_recorded=request.user,
                match_result_log_instance=match_log_entry,
                tournament_chart_instance=tournament  # Pass the tournament instance
            )
        except Exception as e_notify:
            # Log notification error specifically, but don't let it break the main flow
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending email notification: {str(e_notify)}")
            # Optionally, add a message to the user or specific handling if notifications are critical
            # For now, just log and continue.

        # Send Signal notification
        try:
            send_signal_notification(
                user_who_recorded=request.user,
                match_result_log_instance=match_log_entry,
                tournament_chart_instance=tournament  # Pass the tournament instance
            )
        except Exception as e_notify_signal:
            import logging # Ensure logger is available
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending Signal notification: {str(e_notify_signal)}")
            # Log and continue, similar to email.

        # Update player scores
        # Get automatic wins from the tournament archetype if applicable
        from ..models.tournament_types import get_implementation
        archetype_impl = None
        automatic_wins_map = {}
        if hasattr(tournament, 'archetype') and tournament.archetype:
            archetype_impl = get_implementation(tournament.archetype)
            if archetype_impl and hasattr(archetype_impl, 'get_automatic_wins'):
                automatic_wins_map = archetype_impl.get_automatic_wins(len(players))

        # Determine if this is a MoC tournament (sets count as separate matches)
        is_moc = _is_moc_tournament_helper(tournament)

        # Sort players by ranking to get their seed index
        sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)
        player_to_seed = {p.id: idx for idx, p in enumerate(sorted_players)}

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

            # For MoC tournaments, count each set as a separate match
            # For other tournaments, count matchups as matches
            if is_moc:
                player_score.matches_played = sum(m.scores.count() for m in all_played)
            else:
                player_score.matches_played = all_played.count()

            player_score.wins = 0
            player_score.total_point_difference = 0

            # Set automatic wins
            player_seed = player_to_seed.get(player.id, -1)
            player_score.automatic_wins = automatic_wins_map.get(player_seed, 0)

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

            # Add automatic wins to total wins
            player_score.wins += player_score.automatic_wins
            player_score.save()
            
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        # Log the error and return a helpful error message
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving match result: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Error saving score: {str(e)}'})
