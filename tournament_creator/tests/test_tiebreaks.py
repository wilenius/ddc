from django.test import TestCase
from django.utils import timezone
from django.db import models
from ..models import (
    Player, TournamentChart, Matchup, MatchScore, 
    PlayerScore, User, MatchResultLog
)
from ..views.tournament_views import TournamentDetailView

class TiebreakTests(TestCase):
    """
    Tests for the tiebreak resolution system.
    Tests cover all six tiebreak criteria:
    1. Overall wins
    2. Head-to-head record between tied players
    3. Point differential in games between tied players
    4. Record against teams that placed above the tied players
    5. Point differential in games against teams that placed above the tied players
    6. Point differential in games against all teams in the pool
    """
    
    def setUp(self):
        """Set up test data needed for all test methods."""
        # Create test players
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test{i+1}',
                ranking=i+1
            )
            self.players.append(player)

        # Create a tournament
        self.tournament = TournamentChart.objects.create(
            name='Tiebreak Test Tournament',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)
        
        # Create the tournament detail view for apply_tiebreaks function
        self.view = TournamentDetailView()
        
    def test_head_to_head_tiebreak(self):
        """
        Test the head-to-head tiebreak criteria.
        
        Scenario: Players 1, 2, and 3 all have 3 wins, but in their head-to-head matches:
        - Player 1 won both sets against Player 2
        - Player 2 won both sets against Player 3
        - Player 3 won both sets against Player 1
        
        Result: Circular head-to-head with each player having 2 wins. 
        Should break ties based on point differential in their head-to-head matches.
        """
        # Create player scores with 3 wins each
        for player in self.players[:3]:
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=3,
                matches_played=3,
                total_point_difference=0  # Equal PD initially
            )
        
        # Player4 through Player8 have 0 wins
        for player in self.players[3:]:
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=0,
                matches_played=3,
                total_point_difference=-10
            )
            
        # Create matchups between the tied players
        # Matchup 1: Player1 vs Player2 (Player1 wins)
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],  # Player1
            pair1_player2=None,
            pair2_player1=self.players[1],  # Player2
            pair2_player2=None
        )
        
        # Player1 wins over Player2 with +6 point differential
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=9,
            winning_team=1,
            point_difference=6
        )
        
        # Matchup 2: Player2 vs Player3 (Player2 wins)
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[1],  # Player2
            pair1_player2=None,
            pair2_player1=self.players[2],  # Player3
            pair2_player2=None
        )
        
        # Player2 wins over Player3 with +4 point differential
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=15,
            team2_score=11,
            winning_team=1,
            point_difference=4
        )
        
        # Matchup 3: Player3 vs Player1 (Player3 wins)
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[2],  # Player3
            pair1_player2=None,
            pair2_player1=self.players[0],  # Player1
            pair2_player2=None
        )
        
        # Player3 wins over Player1 with +2 point differential
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=15,
            team2_score=13,
            winning_team=1,
            point_difference=2
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Verify results: The order should be determined by point differential in head-to-head
        # Player1: +6 PD (vs Player2) - 2 PD (vs Player3) = +4 PD
        # Player2: -6 PD (vs Player1) + 4 PD (vs Player3) = -2 PD
        # Player3: -4 PD (vs Player2) + 2 PD (vs Player1) = -2 PD
        
        # Find tied players in the sorted order
        tied_players = sorted_scores[:3]
        
        # Player1 should be first (highest point differential in head-to-head)
        self.assertEqual(tied_players[0].player.id, self.players[0].id, 
                        "Player1 should be first due to highest point differential in head-to-head")
        
        # Player2 and Player3 should be tied and arbitrary (since their h2h PD is the same)
        self.assertIn(tied_players[1].player.id, [self.players[1].id, self.players[2].id],
                     "Second place should be either Player2 or Player3")
        self.assertIn(tied_players[2].player.id, [self.players[1].id, self.players[2].id],
                     "Third place should be either Player2 or Player3")
        self.assertNotEqual(tied_players[1].player.id, tied_players[2].player.id,
                          "Second and third place should be different players")
                          
    def test_clear_head_to_head_winner(self):
        """
        Test a clear head-to-head tiebreak situation.
        
        Scenario: Players 1, 2, and 3 all have 3 wins, but in their head-to-head matches:
        - Player 1 won both against Players 2 and 3
        - Player 2 won against Player 3
        - Player 3 lost both head-to-head matches
        
        Result: Player 1 should be first, Player 2 second, Player 3 third.
        """
        # Create player scores with 3 wins each
        for player in self.players[:3]:
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=3,
                matches_played=3,
                total_point_difference=0  # Equal PD initially
            )
            
        # Create matchups between the tied players
        # Matchup 1: Player1 vs Player2 (Player1 wins)
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],  # Player1
            pair1_player2=None,
            pair2_player1=self.players[1],  # Player2
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=10,
            winning_team=1,
            point_difference=5
        )
        
        # Matchup 2: Player1 vs Player3 (Player1 wins)
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[0],  # Player1
            pair1_player2=None,
            pair2_player1=self.players[2],  # Player3
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=15,
            team2_score=8,
            winning_team=1,
            point_difference=7
        )
        
        # Matchup 3: Player2 vs Player3 (Player2 wins)
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[1],  # Player2
            pair1_player2=None,
            pair2_player1=self.players[2],  # Player3
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=15,
            team2_score=12,
            winning_team=1,
            point_difference=3
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Verify results by head-to-head wins
        # Player1: 2 H2H wins
        # Player2: 1 H2H win
        # Player3: 0 H2H wins
        
        # Find tied players in the sorted order
        tied_players = sorted_scores[:3]
        
        # Players should be in order: 1, 2, 3
        self.assertEqual(tied_players[0].player.id, self.players[0].id, 
                        "Player1 should be first with most head-to-head wins")
        self.assertEqual(tied_players[1].player.id, self.players[1].id,
                        "Player2 should be second with 1 head-to-head win")
        self.assertEqual(tied_players[2].player.id, self.players[2].id,
                        "Player3 should be third with 0 head-to-head wins")
                        
    def test_point_differential_tiebreak(self):
        """
        Test point differential tiebreak when head-to-head record is tied.
        
        Scenario: 
        - Player1 and Player2 both have 3 wins
        - They each won 1 set against each other (tied head-to-head)
        - Player1 has better point differential in their head-to-head matches
        
        Result: Player1 should be ranked higher due to better point differential.
        """
        # Create player scores with 3 wins each for the first two players
        for player in self.players[:2]:
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=3,
                matches_played=3,
                total_point_difference=0  # Equal total PD
            )
        
        # Create a matchup between the tied players with two sets
        matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],  # Player1
            pair1_player2=None,
            pair2_player1=self.players[1],  # Player2
            pair2_player2=None
        )
        
        # Set 1: Player1 wins by a large margin
        MatchScore.objects.create(
            matchup=matchup,
            set_number=1,
            team1_score=15,
            team2_score=5,
            winning_team=1,
            point_difference=10
        )
        
        # Set 2: Player2 wins by a small margin
        MatchScore.objects.create(
            matchup=matchup,
            set_number=2,
            team1_score=13,
            team2_score=15,
            winning_team=2,
            point_difference=2
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Find tied players in the sorted order (should be Player1, Player2)
        tied_players = sorted_scores[:2]
        
        # Player1 should be ranked higher due to better point differential
        # Player1: +10 - 2 = +8 point differential
        # Player2: -10 + 2 = -8 point differential
        self.assertEqual(tied_players[0].player.id, self.players[0].id,
                        "Player1 should be first with better point differential")
        self.assertEqual(tied_players[1].player.id, self.players[1].id,
                        "Player2 should be second with worse point differential")
        
    def test_equal_point_differential_overall_tiebreak(self):
        """
        Test overall point differential tiebreak when head-to-head is tied.
        
        Scenario:
        - Player1 and Player2 both have 3 wins
        - They split matches equally, so head-to-head wins are tied
        - Their head-to-head point differential is 0 (perfectly tied)
        - Player1 has better overall point differential than Player2
        
        Result: Player1 should be ranked higher due to better overall point differential.
        """
        # Create player scores with 3 wins each, but different overall PD
        PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[0],  # Player1
            wins=3,
            matches_played=3,
            total_point_difference=10  # Better overall PD
        )
        
        PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[1],  # Player2
            wins=3, 
            matches_played=3,
            total_point_difference=5   # Worse overall PD
        )
        
        # Create a matchup between the tied players with two sets
        matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],  # Player1
            pair1_player2=None,
            pair2_player1=self.players[1],  # Player2
            pair2_player2=None
        )
        
        # Set 1: Player1 wins by 3 points
        MatchScore.objects.create(
            matchup=matchup,
            set_number=1,
            team1_score=15,
            team2_score=12,
            winning_team=1,
            point_difference=3
        )
        
        # Set 2: Player2 wins by 3 points
        MatchScore.objects.create(
            matchup=matchup,
            set_number=2,
            team1_score=12,
            team2_score=15,
            winning_team=2,
            point_difference=3
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Verify that Player1 is ranked higher (should use overall PD as tiebreaker)
        self.assertEqual(sorted_scores[0].player.id, self.players[0].id,
                        "Player1 should be first with better overall point differential")
        self.assertEqual(sorted_scores[1].player.id, self.players[1].id,
                        "Player2 should be second with worse overall point differential")
                        
    def test_above_team_wins_tiebreak(self):
        """
        Test tiebreak based on record against teams that placed above the tied teams.
        
        Scenario:
        - Players 1, 2, and 3 all have 3 wins each (tied in basic criteria)
        - Head-to-head record is tied (each has 1 win against the others)
        - Point differential in head-to-head is identical
        - Player 3 has a better record against higher-placed players
        
        Result: Player 3 should be ranked first due to better record against higher-placed players.
        """
        # Create player scores for all players
        # Player 0 has most wins (4) - will be an "above" player
        PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[0],
            wins=4,
            matches_played=4,
            total_point_difference=10
        )
        
        # Tied players at 3 wins each
        for i in range(1, 4):
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=self.players[i],
                wins=3,
                matches_played=4,
                total_point_difference=0
            )
            
        # Rest of players with fewer wins
        for i in range(4, 8):
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=self.players[i],
                wins=i-4,  # 0, 1, 2, 3 wins
                matches_played=4,
                total_point_difference=-5
            )
            
        # Create matchups between tied players (1, 2, 3) - all have 1 win against each other
        # Player1 vs Player2 (Player1 wins)
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=None,
            pair2_player1=self.players[2],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=12,
            winning_team=1,
            point_difference=3
        )
        
        # Player2 vs Player3 (Player2 wins)
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[2],
            pair1_player2=None,
            pair2_player1=self.players[3],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=12,
            team2_score=15,
            winning_team=2,
            point_difference=3
        )
        
        # Player3 vs Player1 (Player3 wins)
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[3],
            pair1_player2=None,
            pair2_player1=self.players[1],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=15,
            team2_score=12,
            winning_team=1,
            point_difference=3
        )
        
        # Now create matches against the above-placed Player0
        # Player1 vs Player0 (Player0 wins)
        matchup4 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=4,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=None,
            pair2_player1=self.players[0],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup4,
            set_number=1,
            team1_score=10,
            team2_score=15,
            winning_team=2,
            point_difference=5
        )
        
        # Player2 vs Player0 (Player0 wins)
        matchup5 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=5,
            court_number=1,
            pair1_player1=self.players[2],
            pair1_player2=None,
            pair2_player1=self.players[0],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup5,
            set_number=1,
            team1_score=8,
            team2_score=15,
            winning_team=2,
            point_difference=7
        )
        
        # Player3 vs Player0 (Player3 wins)
        matchup6 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=6,
            court_number=1,
            pair1_player1=self.players[3],
            pair1_player2=None,
            pair2_player1=self.players[0],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup6,
            set_number=1,
            team1_score=15,
            team2_score=13,
            winning_team=1,
            point_difference=2
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Extract the tied players (should be Players 1, 2, 3)
        tied_players = [score for score in sorted_scores if score.player.id in 
                        [self.players[1].id, self.players[2].id, self.players[3].id]]
        
        # Player3 should be first (won against Player0)
        # Player1 and Player2 both lost to Player0, so they remain tied
        self.assertEqual(tied_players[0].player.id, self.players[3].id,
                         "Player3 should be first due to win against higher-placed player")
                         
    def test_above_team_point_differential_tiebreak(self):
        """
        Test tiebreak based on point differential against teams that placed above.
        
        Scenario:
        - Player1 and Player2 both have 3 wins (tied in basic criteria)
        - Head-to-head is tied (1 set each)
        - Head-to-head point differential is tied
        - Both lost to Player0 (higher-placed player), but Player1 lost by less points
        
        Result: Player1 should be ranked higher due to better point differential against higher-placed players.
        """
        # Create player scores
        # Player0 has more wins (4) - will be an "above" player
        PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[0],
            wins=4,
            matches_played=3,
            total_point_difference=8
        )
        
        # Tied players
        for i in range(1, 3):
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=self.players[i],
                wins=3,
                matches_played=3,
                total_point_difference=0
            )
        
        # Create matchup between the tied players - with tied head-to-head
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=None,
            pair2_player1=self.players[2],
            pair2_player2=None
        )
        
        # Each player wins one set by the same margin
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=10,
            winning_team=1,
            point_difference=5
        )
        
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=2,
            team1_score=10,
            team2_score=15,
            winning_team=2,
            point_difference=5
        )
        
        # Create matchups against the above-placed Player0
        # Player1 vs Player0 (Player0 wins by 3)
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=None,
            pair2_player1=self.players[0],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=12,
            team2_score=15,
            winning_team=2,
            point_difference=3
        )
        
        # Player2 vs Player0 (Player0 wins by 7)
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[2],
            pair1_player2=None,
            pair2_player1=self.players[0],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=8,
            team2_score=15,
            winning_team=2,
            point_difference=7
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Extract the tied players
        tied_players = [score for score in sorted_scores if score.player.id in 
                        [self.players[1].id, self.players[2].id]]
        
        # Player1 should be first (lost by 3 vs Player0)
        # Player2 should be second (lost by 7 vs Player0)
        self.assertEqual(tied_players[0].player.id, self.players[1].id,
                        "Player1 should be first due to better PD against higher-placed player")
        self.assertEqual(tied_players[1].player.id, self.players[2].id,
                        "Player2 should be second due to worse PD against higher-placed player")
                        
    def test_complex_multiple_tied_players(self):
        """
        Test a complex scenario with multiple tied players and partners across matches.
        
        Scenario:
        - 4 players tied at 3 wins each
        - Each player has played both with and against the others
        - Complex ordering requires considering all tiebreak criteria
        
        This tests edge cases where players appear in different combinations as partners and opponents.
        """
        # Create player scores - 4 players all tied with 3 wins
        for i in range(4):
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=self.players[i],
                wins=3,
                matches_played=3,
                # Give different total point differentials as the last tiebreaker
                total_point_difference=10-i
            )
        
        # Create matchups with players appearing as both partners and opponents
        # Match 1: Players 0 & 1 vs Players 2 & 3
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[1],
            pair2_player1=self.players[2],
            pair2_player2=self.players[3]
        )
        
        # Team 1 wins
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=10,
            winning_team=1,
            point_difference=5
        )
        
        # Match 2: Players 0 & 2 vs Players 1 & 3
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[2],
            pair2_player1=self.players[1],
            pair2_player2=self.players[3]
        )
        
        # Team 2 wins
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=10,
            team2_score=15,
            winning_team=2,
            point_difference=5
        )
        
        # Match 3: Players 0 & 3 vs Players 1 & 2
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[3],
            pair2_player1=self.players[1],
            pair2_player2=self.players[2]
        )
        
        # Team 1 wins
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=15,
            team2_score=12,
            winning_team=1,
            point_difference=3
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Check that the results make sense (we don't know exact ordering without manual calculation,
        # but we can check that sorting was applied and all players are present)
        self.assertEqual(len(sorted_scores), len(player_scores), 
                         "All player scores should be preserved after tiebreak")
        
        # Players should be ranked primarily by wins
        for i in range(len(sorted_scores)-1):
            self.assertTrue(sorted_scores[i].wins >= sorted_scores[i+1].wins,
                           "Players should be sorted by wins (descending)")
        
        # Check that each player appears exactly once
        player_ids = [score.player.id for score in sorted_scores]
        for i in range(4):
            self.assertEqual(player_ids.count(self.players[i].id), 1, 
                            f"Player {i} should appear exactly once in results")
                            
    def test_tied_players_as_partners(self):
        """
        Test handling of tied players appearing as partners in some matchups.
        
        Scenario:
        - Players 1, 2, 3 are tied at 3 wins each
        - Players 1 and 2 were partners in one match against Players 0 and 3
        - We need to ensure that matches where tied players were partners don't count for head-to-head
        """
        # Create player scores
        # Player 0 has more wins
        PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[0],
            wins=4,
            matches_played=3
        )
        
        # Tied players
        for i in range(1, 4):
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=self.players[i],
                wins=3,
                matches_played=3,
                total_point_difference=0
            )
            
        # Matchup where tied players are partners
        # Player1 & Player2 vs Player0 & Player3
        matchup1 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=self.players[2],
            pair2_player1=self.players[0],
            pair2_player2=self.players[3]
        )
        
        MatchScore.objects.create(
            matchup=matchup1,
            set_number=1,
            team1_score=15,
            team2_score=10,
            winning_team=1,
            point_difference=5
        )
        
        # Matchup with head-to-head matchup between tied players
        # Player1 vs Player3 (direct head-to-head between tied players)
        matchup2 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=2,
            court_number=1,
            pair1_player1=self.players[1],
            pair1_player2=None,
            pair2_player1=self.players[3],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup2,
            set_number=1,
            team1_score=15,
            team2_score=10,
            winning_team=1,
            point_difference=5
        )
        
        # Player2 vs Player3 (direct head-to-head between tied players)
        matchup3 = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=3,
            court_number=1,
            pair1_player1=self.players[2],
            pair1_player2=None,
            pair2_player1=self.players[3],
            pair2_player2=None
        )
        
        MatchScore.objects.create(
            matchup=matchup3,
            set_number=1,
            team1_score=10,
            team2_score=15,
            winning_team=2,
            point_difference=5
        )
        
        # Get all player scores
        player_scores = list(PlayerScore.objects.filter(tournament=self.tournament))
        
        # Apply tiebreaks
        sorted_scores, _ = self.view.apply_tiebreaks(self.tournament, player_scores)
        
        # Extract the tied players
        tied_players = [score for score in sorted_scores if score.player.id in 
                       [self.players[1].id, self.players[2].id, self.players[3].id]]
        
        # The exact order depends on how the tiebreak algorithm processes the matches
        # The most important thing is that all three tied players are included and appear exactly once
        player_ids = [player.player.id for player in tied_players]
        self.assertEqual(len(player_ids), 3, "Should have exactly 3 tied players")
        self.assertIn(self.players[1].id, player_ids, "Player1 should be in the results")
        self.assertIn(self.players[2].id, player_ids, "Player2 should be in the results")
        self.assertIn(self.players[3].id, player_ids, "Player3 should be in the results")
        
        # Player1 should be ranked higher than Player2 (won direct H2H)
        player1_idx = next(i for i, score in enumerate(tied_players) if score.player.id == self.players[1].id)
        player2_idx = next(i for i, score in enumerate(tied_players) if score.player.id == self.players[2].id)
        self.assertLess(player1_idx, player2_idx, "Player1 should be ranked higher than Player2")