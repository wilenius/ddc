"""
Provides comprehensive tests for the tournament tiebreaking logic, focusing on 
verifying not only the final player rankings but also the step-by-step 
reasoning behind tiebreak decisions.

This test suite utilizes the `apply_tiebreaks` method from 
`tournament_creator.views.tournament_views.TournamentDetailView`, which is 
expected to return a `reasoning_log` (a list of strings) alongside the 
sorted player list. This log is crucial for understanding how ties were resolved.

When adding new tests:
- Use the helper methods in `ComprehensiveTiebreakTestHelpers` to set up 
  players, tournaments, player scores, and match results.
- Ensure assertions cover both the final sorted order of players and the 
  presence of key phrases or data points within the `reasoning_log` to 
  validate the decision-making process.
- Clearly document the scenario being tested in the test method's docstring.
"""
from django.test import TestCase
from django.utils import timezone
from ..models import Player, TournamentChart, Matchup, MatchScore, PlayerScore, User
from ..views.tournament_views import TournamentDetailView

class ComprehensiveTiebreakTestHelpers:
    """
    Contains helper methods to facilitate the creation of test data 
    (players, tournaments, scores, match results) for tiebreak scenarios.
    These methods are designed to make test setup more concise and readable.
    """
    @staticmethod
    def create_players(player_names):
        """
        Helper to create multiple Player instances.

        Args:
            player_names (list[tuple[str, str]]): A list of tuples, where each 
                tuple contains (first_name, last_name_prefix). 
                Example: [('Alice', 'A'), ('Bob', 'B')]

        Returns:
            list[Player]: A list of the created Player objects.
        """
        players = []
        for i, (first, last_prefix) in enumerate(player_names):
            player = Player.objects.create(
                first_name=first,
                last_name=f'{last_prefix}son', # Creates a simple unique last name
                ranking=i + 1 # Assigns a basic ranking
            )
            players.append(player)
        return players

    @staticmethod
    def create_tournament(name="Test Tiebreak Tournament", players_list=None, num_rounds=3):
        """
        Helper to create a TournamentChart instance.

        Args:
            name (str, optional): The name of the tournament. 
                Defaults to "Test Tiebreak Tournament".
            players_list (list[Player], optional): A list of Player objects to 
                associate with the tournament. Defaults to None.
            num_rounds (int, optional): The number of rounds for the tournament.
                Defaults to 3.

        Returns:
            TournamentChart: The created TournamentChart object.
        """
        tournament = TournamentChart.objects.create(
            name=name,
            date=timezone.now().date(),
            number_of_rounds=num_rounds, 
            number_of_courts=1  # Defaulting to 1 court for simplicity in tests
        )
        if players_list:
            tournament.players.set(players_list)
        return tournament

    @staticmethod
    def setup_player_scores(tournament, player_score_data):
        """
        Helper to create multiple PlayerScore instances for a given tournament.

        Args:
            tournament (TournamentChart): The tournament to which these scores belong.
            player_score_data (list[tuple[Player, dict]]): A list of tuples, 
                where each tuple contains:
                - player_instance (Player): The player for whom the score is recorded.
                - data (dict): A dictionary with score details, e.g., 
                  {'wins': w, 'matches_played': mp, 'total_point_difference': pd}.

        Returns:
            list[PlayerScore]: A list of the created PlayerScore objects.
        """
        scores = []
        for player, data in player_score_data:
            score = PlayerScore.objects.create(
                tournament=tournament,
                player=player,
                wins=data.get('wins', 0),
                matches_played=data.get('matches_played', 0),
                total_point_difference=data.get('total_point_difference', 0)
            )
            scores.append(score)
        return scores

    @staticmethod
    def record_match_result(tournament, team1_players, team2_players, team1_actual_score, team2_actual_score, round_num=1, court_num=1, set_num=1):
        """
        Records a match result (a Matchup and its associated MatchScore) 
        between two teams. Assumes singles or doubles based on list length.

        Args:
            tournament (TournamentChart): The tournament where the match occurred.
            team1_players (list[Player]): List of Player objects for team 1.
            team2_players (list[Player]): List of Player objects for team 2.
            team1_actual_score (int): The score achieved by team 1.
            team2_actual_score (int): The score achieved by team 2.
            round_num (int, optional): The round number of the match. Defaults to 1.
            court_num (int, optional): The court number of the match. Defaults to 1.
            set_num (int, optional): The set number for the score. Defaults to 1.

        Returns:
            MatchScore: The created MatchScore object.
        
        Raises:
            ValueError: If either team1_players or team2_players is empty.
        """
        if not team1_players or not team2_players:
            raise ValueError("Both teams must have at least one player.")

        # Create the matchup
        matchup = Matchup.objects.create(
            tournament_chart=tournament,
            round_number=round_num,
            court_number=court_num,
            pair1_player1=team1_players[0],
            pair1_player2=team1_players[1] if len(team1_players) > 1 else None,
            pair2_player1=team2_players[0],
            pair2_player2=team2_players[1] if len(team2_players) > 1 else None,
        )

        # Record the score for the matchup
        match_score = MatchScore.objects.create(
            matchup=matchup,
            set_number=set_num,
            team1_score=team1_actual_score,
            team2_score=team2_actual_score
            # winning_team and point_difference are calculated automatically on MatchScore.save()
        )
        return match_score


class TestComprehensiveTiebreaks(TestCase):
    """
    Test suite for validating tiebreak logic and the detailed reasoning output
    from the `apply_tiebreaks` method in TournamentDetailView.
    """
    def setUp(self):
        """
        Set up common test data and instances needed for tiebreak tests.
        This includes a set of players, a default tournament, and an instance
        of the TournamentDetailView which contains the apply_tiebreaks logic.
        """
        self.helpers = ComprehensiveTiebreakTestHelpers()
        
        # Common players for use across tests
        self.player_names_setup = [('Alice', 'A'), ('Bob', 'B'), ('Charlie', 'C'), ('David', 'D')]
        self.all_players_setup = self.helpers.create_players(self.player_names_setup)
        self.alice, self.bob, self.charlie, self.david = self.all_players_setup

        # A default tournament instance; tests can override or use this directly
        self.tournament = self.helpers.create_tournament(players_list=self.all_players_setup)
        
        # The TournamentDetailView instance contains the apply_tiebreaks method
        self.tiebreak_resolver = TournamentDetailView()

        # A dummy user, in case any part of the process requires an authenticated user
        self.user = User.objects.create_user(username='testresolver', password='password', role='ADMIN')

    def test_simple_head_to_head(self):
        """
        Tests a two-way tie resolved by a direct head-to-head match.
        - Scenario: Alice and Bob are tied with 2 wins. Charlie has 1 win.
        - H2H Match: Alice played and won against Bob (15-10).
        - Expected order: Alice, Bob, Charlie.
        - Expected reasoning: Log should clearly state Alice and Bob are tied, 
          that the head-to-head rule is applied, show Alice's win and Bob's loss 
          in H2H stats, and the resulting order for the tied group.
        """
        # Define players specifically for this test scenario
        players_for_test = [self.alice, self.bob, self.charlie]
        self.tournament.players.set(players_for_test) # Isolate players for this tournament

        # Setup initial scores: Alice and Bob tied on wins and total point difference
        self.helpers.setup_player_scores(
            self.tournament,
            [
                (self.alice, {'wins': 2, 'matches_played': 2, 'total_point_difference': 10}),
                (self.bob, {'wins': 2, 'matches_played': 2, 'total_point_difference': 10}),
                (self.charlie, {'wins': 1, 'matches_played': 2, 'total_point_difference': 5}),
            ]
        )

        # Record the crucial Head-to-Head Match: Alice defeats Bob
        # This match result is key to breaking the tie between Alice and Bob.
        self.helpers.record_match_result(self.tournament, [self.alice], [self.bob], 15, 10, round_num=1)

        # Retrieve player scores for tiebreaking
        player_scores_qs = PlayerScore.objects.filter(tournament=self.tournament, player__in=players_for_test).order_by('-wins', '-total_point_difference')
        initial_player_scores = list(player_scores_qs)

        # Apply the tiebreak logic
        sorted_players, reasoning_log = self.tiebreak_resolver.apply_tiebreaks(self.tournament, initial_player_scores)
        full_reasoning_text = "\n".join(reasoning_log) # For easier substring searching

        # Assertions for correct player order
        self.assertEqual(len(sorted_players), 3, "Should be 3 players in the sorted list.")
        self.assertEqual(sorted_players[0].player, self.alice, "Alice should be ranked first.")
        self.assertEqual(sorted_players[1].player, self.bob, "Bob should be ranked second.")
        self.assertEqual(sorted_players[2].player, self.charlie, "Charlie should be ranked third.")

        # Assertions for key details in the reasoning log
        self.assertIn(f"Group tied with 2 wins: Alice, Bob.", full_reasoning_text, "Log should identify Alice and Bob as tied.")
        self.assertIn(f"Processing tiebreak for group: Alice, Bob (all with 2 wins).", full_reasoning_text, "Log should process the Alice-Bob tie.")
        self.assertIn(f"Tiebreak Criterion 2 & 3: Head-to-Head within the group.", full_reasoning_text, "Log should state H2H criterion is used.")
        # Alice's H2H stats: 1 win, +5 Point Difference (15-10)
        self.assertIn(f"  Alice (H2H Wins: 1, H2H PD: 5)", full_reasoning_text, "Alice's H2H stats incorrect in log.")
        # Bob's H2H stats: 0 wins, -5 Point Difference (10-15)
        self.assertIn(f"  Bob (H2H Wins: 0, H2H PD: -5)", full_reasoning_text, "Bob's H2H stats incorrect in log.")
        self.assertIn(f"Sorted order for this group: Alice, Bob.", full_reasoning_text, "Log should show correct sorted order for the tied group.")
        self.assertIn(f"Final sorted order: Alice, Bob, Charlie", full_reasoning_text, "Log should confirm the final overall ranking.")


    def test_three_way_h2h_point_differential(self):
        """
        Tests a three-way tie where H2H wins are also tied, resolved by H2H point differential.
        - Scenario: Alice, Bob, Charlie all tied with 2 wins and same overall PD.
        - H2H Matches (circular wins, different PDs):
            - Alice beats Bob: 15-10 (Alice H2H PD vs Bob: +5)
            - Bob beats Charlie: 15-12 (Bob H2H PD vs Charlie: +3)
            - Charlie beats Alice: 15-13 (Charlie H2H PD vs Alice: +2)
        - Aggregate H2H PDs:
            - Alice: (+5 vs Bob) + (-2 vs Charlie) = +3
            - Bob: (-5 vs Alice) + (+3 vs Charlie) = -2
            - Charlie: (-3 vs Bob) + (+2 vs Alice) = -1
        - Expected order: Alice (highest H2H PD), Charlie, Bob.
        - Expected reasoning: Log should show the 3-way tie, H2H wins tied (1 each), 
          then resolution by H2H PD with correct values for each player.
        """
        players_for_test = [self.alice, self.bob, self.charlie]
        self.tournament.players.set(players_for_test)
        self.tournament.number_of_rounds = 3 # Ensure enough rounds for the H2H matches
        self.tournament.save()

        # Initial Scores: All three tied on wins and total point difference
        base_pd = 10 # Arbitrary, to ensure overall PD doesn't break the tie prematurely
        self.helpers.setup_player_scores(
            self.tournament,
            [
                (self.alice, {'wins': 2, 'matches_played': 3, 'total_point_difference': base_pd}),
                (self.bob, {'wins': 2, 'matches_played': 3, 'total_point_difference': base_pd}),
                (self.charlie, {'wins': 2, 'matches_played': 3, 'total_point_difference': base_pd}),
            ]
        )

        # Record Head-to-Head Matches to create the circular H2H win scenario
        self.helpers.record_match_result(self.tournament, [self.alice], [self.bob], 15, 10, round_num=1)     # Alice +5, Bob -5
        self.helpers.record_match_result(self.tournament, [self.bob], [self.charlie], 15, 12, round_num=2)  # Bob +3, Charlie -3
        self.helpers.record_match_result(self.tournament, [self.charlie], [self.alice], 15, 13, round_num=3) # Charlie +2, Alice -2

        player_scores_qs = PlayerScore.objects.filter(tournament=self.tournament, player__in=players_for_test).order_by('-wins', '-total_point_difference')
        initial_player_scores = list(player_scores_qs)

        sorted_players, reasoning_log = self.tiebreak_resolver.apply_tiebreaks(self.tournament, initial_player_scores)
        full_reasoning_text = "\n".join(reasoning_log)
        
        # Assert final player order based on calculated H2H Point Differentials
        self.assertEqual(len(sorted_players), 3, "Should be 3 players in the sorted list.")
        self.assertEqual(sorted_players[0].player, self.alice, "Alice should be first (H2H PD: +3).")
        self.assertEqual(sorted_players[1].player, self.charlie, "Charlie should be second (H2H PD: -1).")
        self.assertEqual(sorted_players[2].player, self.bob, "Bob should be third (H2H PD: -2).")

        # Assertions for reasoning log
        self.assertIn(f"Group tied with 2 wins: Alice, Bob, Charlie.", full_reasoning_text, "Log should identify the 3-way tie.")
        self.assertIn(f"Processing tiebreak for group: Alice, Bob, Charlie (all with 2 wins).", full_reasoning_text, "Log should process this specific group.")
        # Check H2H stats, specifically that H2H wins are 1 for each, and PDs match calculations
        self.assertIn(f"  Alice (H2H Wins: 1, H2H PD: 3)", full_reasoning_text, "Alice's H2H stats incorrect.")
        self.assertIn(f"  Bob (H2H Wins: 1, H2H PD: -2)", full_reasoning_text, "Bob's H2H stats incorrect.")
        self.assertIn(f"  Charlie (H2H Wins: 1, H2H PD: -1)", full_reasoning_text, "Charlie's H2H stats incorrect.")
        # The fact that H2H wins are all 1 implies this criterion was tied, leading to H2H PD.
        self.assertIn(f"Sorted order for this group: Alice, Charlie, Bob.", full_reasoning_text, "Log should show correct H2H PD sorted order.")
        self.assertIn(f"Final sorted order: Alice, Charlie, Bob", full_reasoning_text, "Log should confirm final overall ranking.")


    def test_overall_point_differential(self):
        """
        Tests tiebreak by overall tournament point differential when H2H is inconclusive.
        - Scenario: Alice and Bob tied on wins. Charlie is third.
        - H2H Match: No direct match played between Alice and Bob.
        - Overall PD: Bob has a better overall tournament point differential (+5) than Alice (0).
        - Expected order: Bob, Alice, Charlie.
        - Expected reasoning: Log should show Alice and Bob tied, H2H inconclusive (0 wins, 0 PD for both),
          then use of overall point differential, showing Bob's higher PD.
        """
        players_for_test = [self.alice, self.bob, self.charlie]
        self.tournament.players.set(players_for_test)

        # Initial Scores: Alice and Bob tied on wins, but Bob has better overall PD.
        self.helpers.setup_player_scores(
            self.tournament,
            [
                (self.alice, {'wins': 2, 'matches_played': 2, 'total_point_difference': 0}),
                (self.bob, {'wins': 2, 'matches_played': 2, 'total_point_difference': 5}), 
                (self.charlie, {'wins': 1, 'matches_played': 2, 'total_point_difference': -5}),
            ]
        )
        
        # Crucially, NO Head-to-Head Match is recorded between Alice and Bob for this test.
        # Their wins come from matches against other players (e.g., David, or hypothetical others).
        # This makes their H2H record 0 wins, 0 PD against each other.

        player_scores_qs = PlayerScore.objects.filter(tournament=self.tournament, player__in=players_for_test).order_by('-wins', '-total_point_difference')
        initial_player_scores = list(player_scores_qs) # Initial sort will put Bob ahead of Alice due to overall PD

        # Apply tiebreaks
        sorted_players, reasoning_log = self.tiebreak_resolver.apply_tiebreaks(self.tournament, initial_player_scores)
        full_reasoning_text = "\n".join(reasoning_log)
        
        # Expected order: Bob (better overall PD), Alice, Charlie
        self.assertEqual(len(sorted_players), 3, "Should be 3 players in the sorted list.")
        self.assertEqual(sorted_players[0].player, self.bob, "Bob should be first due to better overall PD.")
        self.assertEqual(sorted_players[1].player, self.alice, "Alice should be second.")
        self.assertEqual(sorted_players[2].player, self.charlie, "Charlie should be third.")

        # Assertions for reasoning log
        # Note: Initial sort by wins then total_point_difference means Bob might be listed before Alice
        # in the "Group tied..." message if their win counts are the same.
        self.assertIn(f"Group tied with 2 wins: Bob, Alice.", full_reasoning_text, "Log should identify Bob and Alice as tied.")
        self.assertIn(f"Processing tiebreak for group: Bob, Alice (all with 2 wins).", full_reasoning_text, "Log should process the Bob-Alice tie.")
        
        # Verify H2H stats are zero as they didn't play each other
        self.assertIn(f"  Bob (H2H Wins: 0, H2H PD: 0)", full_reasoning_text, "Bob's H2H stats should be zero.")
        self.assertIn(f"  Alice (H2H Wins: 0, H2H PD: 0)", full_reasoning_text, "Alice's H2H stats should be zero.")
        
        # Verify that overall point differential (Criterion 6) is cited and values are correct
        self.assertIn(f"Tiebreak Criterion 6: Total point differential", full_reasoning_text, "Log should indicate use of overall PD.")
        self.assertIn(f"  Bob (Total PD: 5)", full_reasoning_text, "Bob's total PD incorrect in log.")
        self.assertIn(f"  Alice (Total PD: 0)", full_reasoning_text, "Alice's total PD incorrect in log.")
        
        self.assertIn(f"Sorted order for this group: Bob, Alice.", full_reasoning_text, "Log should show Bob sorted above Alice for the group.")
        self.assertIn(f"Final sorted order: Bob, Alice, Charlie", full_reasoning_text, "Log should confirm final overall ranking.")

# Further tests can be added here, following the same pattern of setting up specific
# scenarios and asserting both the final player order and the reasoning log details.
# For example, tests for criteria 4 (wins vs. 'above' teams) and 5 (PD vs. 'above' teams)
# would require more complex setups with more players and defined 'above' groups.
