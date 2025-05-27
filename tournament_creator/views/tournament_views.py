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
        player_scores_qs = PlayerScore.objects.filter(tournament=tournament)
        
        # Apply advanced tiebreak sorting
        # sorted_player_scores, reasoning_log = self.apply_tiebreaks(tournament, list(player_scores_qs))
        # For now, we'll call it and ignore the reasoning log in this view context
        # The new test file will specifically check the reasoning_log
        player_scores, _ = self.apply_tiebreaks(tournament, list(player_scores_qs))
        
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
        Returns a tuple: (sorted_player_scores, reasoning_log)
        Tiebreak order:
        1. Overall wins
        2. Head-to-head record between tied players
        3. Point differential in games between tied players
        4. Record against teams that placed above the initial set of tied teams
        5. Point differential in games against teams that placed above the initial set of tied teams
        6. Point differential in games against all teams in the pool
        """
        reasoning_log = []
        # First sort by wins and total point differential (basic sort)
        # This also serves as the final tiebreaker if all else is equal.
        sorted_scores = sorted(player_scores, key=lambda x: (-x.wins, -x.total_point_difference))
        reasoning_log.append(f"Initial sort based on wins, then total point difference.")
        
        # Look for groups of players with the same number of wins
        groups_of_tied_players = []
        current_group = []
        current_wins = None
        
        # Use a temporary list for finding groups to avoid modifying sorted_scores directly yet
        temp_sorted_for_grouping = list(sorted_scores)

        for score in temp_sorted_for_grouping:
            if current_wins is None or score.wins == current_wins:
                current_group.append(score)
                current_wins = score.wins
            else:
                if len(current_group) > 1:  # Only record groups with ties
                    groups_of_tied_players.append(list(current_group))
                    player_names = ", ".join([ps.player.first_name for ps in current_group])
                    reasoning_log.append(f"Group tied with {current_group[0].wins} wins: {player_names}.")
                current_group = [score]
                current_wins = score.wins
        
        # Add the last group if it has ties
        if len(current_group) > 1:
            groups_of_tied_players.append(list(current_group))
            player_names = ", ".join([ps.player.first_name for ps in current_group])
            reasoning_log.append(f"Group tied with {current_group[0].wins} wins: {player_names}.")
        
        # No ties, return the basic sort
        if not groups_of_tied_players:
            reasoning_log.append("No ties found based on wins. Initial sort is final.")
            return sorted_scores, reasoning_log
            
        # Get all matchups in this tournament with scores
        all_matchups = Matchup.objects.filter(
            tournament_chart=tournament,
            scores__isnull=False
        ).prefetch_related('scores').distinct()
        
        # Process each group of tied players
        for group_idx, group in enumerate(groups_of_tied_players):
            group_player_names = ", ".join([ps.player.first_name for ps in group])
            reasoning_log.append(f"\nProcessing tiebreak for group: {group_player_names} (all with {group[0].wins} wins).")

            tied_player_ids = [score.player.id for score in group]
            
            # --- Determine players "above" this specific group for tiebreak steps 4-5 ---
            # "Above" means players who have more wins than the current group,
            # or players who had the same number of wins but were resolved higher in a previous tiebreak group.
            above_player_ids_for_group = set()
            processed_higher_player_ids = set()

            # Collect IDs from groups processed earlier (these are definitively higher)
            for i in range(group_idx):
                for score in groups_of_tied_players[i]:
                    processed_higher_player_ids.add(score.player.id)
            
            # Collect IDs from players with strictly more wins than the current group
            for score in sorted_scores: # sorted_scores is already sorted by wins
                if score.wins > group[0].wins:
                    above_player_ids_for_group.add(score.player.id)
                elif score.wins == group[0].wins:
                    # If they have the same wins but are in `processed_higher_player_ids`
                    # (meaning they were part of an earlier, now resolved, tie of the same win count)
                    if score.player.id in processed_higher_player_ids:
                         above_player_ids_for_group.add(score.player.id)
                else: # score.wins < group[0].wins
                    break # No need to check further down

            if above_player_ids_for_group:
                above_player_names_for_group = ", ".join([Player.objects.get(id=pid).first_name for pid in above_player_ids_for_group])
                reasoning_log.append(f"Players considered 'above' this group for tiebreaks 4 & 5: {above_player_names_for_group}.")
            else:
                reasoning_log.append(f"No players are ranked 'above' this group for tiebreaks 4 & 5.")

            # Create a record structure to hold all tiebreak criteria
            tiebreak_records = {player_id: {
                'h2h_wins': 0,                 # Head-to-head wins (criterion 2)
                'h2h_point_diff': 0,           # Head-to-head point diff (criterion 3)
                'above_team_wins': 0,          # Wins against higher-placed teams (criterion 4)
                'above_team_point_diff': 0,    # Point diff against higher-placed teams (criterion 5)
                'total_point_diff': group_player_score.total_point_difference # Criterion 6 (already in score object)
            } for player_id in tied_player_ids for group_player_score in group if group_player_score.player.id == player_id}
            
            reasoning_log.append("Tiebreak Criterion 2 & 3: Head-to-Head within the group.")
            # Check each matchup to see if it applies to our tiebreak criteria
            for matchup in all_matchups:
                # Identify players in team 1 and team 2
                match_players_involved_names = []
                team1_players = set()
                team2_players = set()

                if matchup.pair1_player1: 
                    team1_players.add(matchup.pair1_player1_id)
                    match_players_involved_names.append(matchup.pair1_player1.first_name)
                if matchup.pair1_player2: 
                    team1_players.add(matchup.pair1_player2_id)
                    match_players_involved_names.append(matchup.pair1_player2.first_name)
                if matchup.pair2_player1: 
                    team2_players.add(matchup.pair2_player1_id)
                    match_players_involved_names.append(matchup.pair2_player1.first_name)
                if matchup.pair2_player2: 
                    team2_players.add(matchup.pair2_player2_id)
                    match_players_involved_names.append(matchup.pair2_player2.first_name)
                
                match_info_str = f"Match: {' & '.join(match_players_involved_names[:len(team1_players)])} vs {' & '.join(match_players_involved_names[len(team1_players):])}."

                # Find tied players in this matchup
                tied_in_team1 = team1_players.intersection(tied_player_ids)
                tied_in_team2 = team2_players.intersection(tied_player_ids)
                
                is_h2h_match = len(tied_in_team1) > 0 and len(tied_in_team2) > 0
                
                # Identify players from 'above_player_ids_for_group'
                above_in_team1 = team1_players.intersection(above_player_ids_for_group)
                above_in_team2 = team2_players.intersection(above_player_ids_for_group)
                
                for set_score in matchup.scores.all():
                    team1_won = set_score.winning_team == 1
                    set_pd = set_score.point_difference # Absolute PD for the set

                    for player_id in tied_player_ids:
                        on_team1 = player_id in team1_players
                        on_team2 = player_id in team2_players
                        
                        if not (on_team1 or on_team2):
                            continue  # This player wasn't in this match

                        # Player's perspective point differential for this set
                        player_set_pd = 0
                        if on_team1: player_set_pd = set_pd if team1_won else -set_pd
                        if on_team2: player_set_pd = -set_pd if team1_won else set_pd
                            
                        # Update head-to-head records (criterion 2-3)
                        if is_h2h_match:
                            # Log only once per match for H2H consideration
                            # reasoning_log.append(f"  {match_info_str} Considered for H2H.")
                            if (on_team1 and team1_won) or (on_team2 and not team1_won):
                                tiebreak_records[player_id]['h2h_wins'] += 1
                            tiebreak_records[player_id]['h2h_point_diff'] += player_set_pd
                        
                        # Wins/PD against 'above' teams (criterion 4-5)
                        # This player (from tied group) must be playing AGAINST an 'above' player
                        opponent_has_above = (on_team1 and len(above_in_team2) > 0) or \
                                             (on_team2 and len(above_in_team1) > 0)

                        if opponent_has_above:
                            # Log only once per match for vs Above consideration
                            # reasoning_log.append(f"  {match_info_str} Considered for 'vs Above'.")
                            if (on_team1 and team1_won) or (on_team2 and not team1_won):
                                tiebreak_records[player_id]['above_team_wins'] += 1
                            tiebreak_records[player_id]['above_team_point_diff'] += player_set_pd

            for p_id in tied_player_ids:
                p_name = Player.objects.get(id=p_id).first_name
                reasoning_log.append(f"  {p_name} (H2H Wins: {tiebreak_records[p_id]['h2h_wins']}, H2H PD: {tiebreak_records[p_id]['h2h_point_diff']})")

            reasoning_log.append("Tiebreak Criterion 4 & 5: Record against 'above' teams.")
            for p_id in tied_player_ids:
                p_name = Player.objects.get(id=p_id).first_name
                reasoning_log.append(f"  {p_name} (vs Above Wins: {tiebreak_records[p_id]['above_team_wins']}, vs Above PD: {tiebreak_records[p_id]['above_team_point_diff']})")

            reasoning_log.append("Tiebreak Criterion 6: Total point differential (already calculated in PlayerScore).")
            for p_id in tied_player_ids:
                 p_name = Player.objects.get(id=p_id).first_name
                 reasoning_log.append(f"  {p_name} (Total PD: {tiebreak_records[p_id]['total_point_diff']})")

            # Sort the players within this group using all tiebreak criteria
            # The key function now directly uses the calculated tiebreak_records
            group.sort(key=lambda score: (
                -tiebreak_records[score.player.id]['h2h_wins'],
                -tiebreak_records[score.player.id]['h2h_point_diff'],
                -tiebreak_records[score.player.id]['above_team_wins'],
                -tiebreak_records[score.player.id]['above_team_point_diff'],
                -tiebreak_records[score.player.id]['total_point_diff']
            ))
            
            sorted_group_names = ", ".join([ps.player.first_name for ps in group])
            reasoning_log.append(f"Sorted order for this group: {sorted_group_names}.")

            # Store the tiebreak info back into the score objects for display or further use
            for score_item in group:
                player_id = score_item.player.id
                score_item.h2h_wins = tiebreak_records[player_id]['h2h_wins']
                score_item.h2h_point_diff = tiebreak_records[player_id]['h2h_point_diff']
                score_item.above_wins = tiebreak_records[player_id]['above_team_wins'] # Corrected attribute name
                score_item.above_pd = tiebreak_records[player_id]['above_team_point_diff'] # Corrected attribute name
        
        # Rebuild the complete standings list using the (potentially) reordered groups
        final_standings = []
        
        
        # This reconstruction logic needs to be careful.
        # `sorted_scores` is the initial overall sort.
        # `groups_of_tied_players` contains sub-lists that have been internally re-sorted.
        # We need to replace the segments in `sorted_scores` with these re-sorted groups.

        # Create a dictionary from sorted_scores for easy lookup by ID
        # This isn't strictly necessary if we iterate carefully, but can simplify reconstruction.
        
        # A simpler way to reconstruct: Iterate through the original `sorted_scores` (which has the overall structure).
        # If a player in `sorted_scores` is the first player of a group in `groups_of_tied_players`
        # (matched by wins and then checking if they are part of that group),
        # then extend `final_standings` with the re-sorted group and skip ahead in `sorted_scores`.
        
        # Create a map of player_id to its PlayerScore object for easy access
        # This helps in rebuilding the final_standings list correctly.
        player_score_map = {ps.player.id: ps for ps in player_scores}

        # Flatten the groups_of_tied_players into a single list of player_ids in their new sorted order
        resolved_tied_player_ids_in_order = []
        for group in groups_of_tied_players:
            for ps in group:
                resolved_tied_player_ids_in_order.append(ps.player.id)

        # Players not in any tie group
        non_tied_player_ids = [ps.player.id for ps in sorted_scores if ps.player.id not in resolved_tied_player_ids_in_order]

        # Reconstruct final_standings:
        # Start with players who were never in a tie group, in their original sorted order.
        # Then, insert the resolved tied groups in their correct win-based positions.
        
        # This is tricky. The `groups_of_tied_players` are already sorted by their win levels
        # because they were derived from `sorted_scores`.
        # The internal sort only reorders *within* those win levels.

        # Let's try to build `final_standings` by iterating through `sorted_scores` (the initial sort)
        # and replacing segments with the re-sorted groups from `groups_of_tied_players`.
        
        final_standings_player_ids = [ps.player.id for ps in sorted_scores] # Get IDs in initial sorted order
        
        for group in groups_of_tied_players:
            if not group: continue
            
            # Find the starting index of this group in the `final_standings_player_ids`
            # This assumes the first player of the `group` (before its internal tiebreak sort)
            # can be found in `final_standings_player_ids`.
            # This is not robust if the group itself was reordered significantly.

            # A more robust way:
            # Create the final list by processing `sorted_scores`.
            # If a score from `sorted_scores` is part of a group in `groups_of_tied_players`,
            # ensure that the entire re-sorted group is inserted, and skip already added players.
            
            # `groups_of_tied_players` contains lists of PlayerScore objects.
            # These objects are the same instances as in `player_scores` and `sorted_scores`.
            # The `group.sort(...)` operation sorts these lists *in place*.
            
            # So, `sorted_scores` itself is NOT what we should return if ties were broken.
            # We need to construct `final_standings` by inserting the re-sorted `group` lists
            # into the correct positions based on their win counts.

        # The `sorted_scores` list already has players sorted by wins.
        # The `groups_of_tied_players` list contains the sub-groups that were tied by wins.
        # Each `group` in `groups_of_tied_players` has been sorted in place by the tiebreak criteria.

        # We can iterate through the `sorted_scores` list.
        # If a `PlayerScore` object is encountered that is the first element of one of the
        # (now sorted) `group` lists, we append that entire group to `final_standings`
        # and then mark that group as processed (e.g., by setting a flag or removing it).
        # If the `PlayerScore` object is not part of any unprocessed tied group, append it individually.

        processed_group_indices = [False] * len(groups_of_tied_players)
        output_final_standings = []
        
        temp_scores_iter = iter(sorted_scores) # Initial overall sort
        
        try:
            current_score_from_iter = next(temp_scores_iter)
            while True:
                added_group = False
                for i, group in enumerate(groups_of_tied_players):
                    if not processed_group_indices[i] and group and current_score_from_iter.player.id == group[0].player.id:
                        # This `current_score_from_iter` is the start of a (re-sorted) tied group.
                        # Add the entire re-sorted group.
                        output_final_standings.extend(group)
                        processed_group_indices[i] = True
                        
                        # Advance the iterator past the players we just added from the group.
                        for _ in range(len(group)):
                            current_score_from_iter = next(temp_scores_iter, None)
                        if current_score_from_iter is None: break # End of all scores
                        added_group = True
                        break # Restart search for groups with the new current_score_from_iter
                
                if current_score_from_iter is None: break

                if not added_group:
                    # This player was not the start of any (remaining) tied group. Add individually.
                    # This handles players not in ties, or players in a tied group already added.
                    # To prevent duplicates, ensure this player isn't already in output_final_standings
                    # (which can happen if they were part of an already added group but not the head).
                    # This check is essential because `current_score_from_iter` might be a later element
                    # of a group that was just added.
                    
                    # More simply: if a player is already added (via a group), just advance iterator.
                    player_already_added = any(ps.player.id == current_score_from_iter.player.id for ps in output_final_standings)
                    if not player_already_added:
                         output_final_standings.append(current_score_from_iter)
                    current_score_from_iter = next(temp_scores_iter, None) # Advance to next score
                    if current_score_from_iter is None: break
        except StopIteration:
            pass

        final_standings = output_final_standings
        reasoning_log.append(f"\nFinal sorted order: {', '.join([ps.player.first_name for ps in final_standings])}")
        return final_standings, reasoning_log

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
