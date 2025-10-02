from django.test import TestCase
from django.utils import timezone
from django.db import models
from ..models import Player, TournamentChart, Matchup, TournamentArchetype
from ..models.scoring import MatchScore, PlayerScore
from ..models.tournament_types import MonarchOfTheCourt8


class MoCMultiSetTests(TestCase):
    """Tests for multi-set as separate matches functionality in MoC tournaments."""

    def setUp(self):
        """Set up test data."""
        # Create 8 players
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test{i+1}',
                ranking=i+1
            )
            self.players.append(player)

        # Get the 8-player MoC archetype
        self.archetype_db = TournamentArchetype.objects.get(name="8-player Monarch of the Court")

        # Create tournament
        self.tournament = TournamentChart.objects.create(
            name='Test 8-Player MoC',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)

        # Create a sample matchup
        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            pair1_player1=self.players[0],  # Player 1
            pair1_player2=self.players[2],  # Player 3
            pair2_player1=self.players[4],  # Player 5
            pair2_player2=self.players[6],  # Player 7
            round_number=1,
            court_number=1
        )

    def test_single_set_counts_as_one_match(self):
        """Test that a single set counts as one match played."""
        # Record one set: Team 1 wins
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=1,
            team1_score=11,
            team2_score=5
        )

        # Recalculate scores
        from ..views.tournament_views import _is_moc_tournament_helper
        is_moc = _is_moc_tournament_helper(self.tournament)
        self.assertTrue(is_moc, "Tournament should be identified as MoC")

        # Check player scores - each player should have played 1 match
        for player in [self.players[0], self.players[2], self.players[4], self.players[6]]:
            score, _ = PlayerScore.objects.get_or_create(
                tournament=self.tournament,
                player=player
            )
            # Manually calculate like the view does
            all_played = Matchup.objects.filter(
                tournament_chart=self.tournament
            ).filter(
                models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
            ).distinct()

            matches_played = sum(m.scores.count() for m in all_played)
            self.assertEqual(matches_played, 1, f"{player.first_name} should have played 1 match")

    def test_two_sets_count_as_two_matches(self):
        """Test that two sets count as two matches played."""
        # Record two sets: Team 1 wins both
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=1,
            team1_score=11,
            team2_score=5
        )
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=2,
            team1_score=11,
            team2_score=7
        )

        # Check that each player has played 2 matches
        from django.db import models
        for player in [self.players[0], self.players[2], self.players[4], self.players[6]]:
            all_played = Matchup.objects.filter(
                tournament_chart=self.tournament
            ).filter(
                models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
            ).distinct()

            matches_played = sum(m.scores.count() for m in all_played)
            self.assertEqual(matches_played, 2, f"{player.first_name} should have played 2 matches")

    def test_split_sets_give_correct_wl_ratio(self):
        """Test that when each team wins one set, they each get 1-1 record."""
        # Team 1 wins set 1
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=1,
            team1_score=11,
            team2_score=5
        )
        # Team 2 wins set 2
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=2,
            team1_score=7,
            team2_score=11
        )

        # Calculate wins for each player manually
        from django.db import models

        # Players 1 and 3 are on team 1
        for player in [self.players[0], self.players[2]]:
            wins = 0
            losses = 0
            all_played = Matchup.objects.filter(
                tournament_chart=self.tournament
            ).filter(
                models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
            ).distinct()

            for m in all_played:
                for s in m.scores.all():
                    on_team1 = player in [m.pair1_player1, m.pair1_player2]
                    if on_team1 and s.winning_team == 1:
                        wins += 1
                    elif on_team1 and s.winning_team == 2:
                        losses += 1

            self.assertEqual(wins, 1, f"{player.first_name} should have 1 win")
            self.assertEqual(losses, 1, f"{player.first_name} should have 1 loss")

        # Players 5 and 7 are on team 2
        for player in [self.players[4], self.players[6]]:
            wins = 0
            losses = 0
            all_played = Matchup.objects.filter(
                tournament_chart=self.tournament
            ).filter(
                models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
            ).distinct()

            for m in all_played:
                for s in m.scores.all():
                    on_team2 = player in [m.pair2_player1, m.pair2_player2]
                    if on_team2 and s.winning_team == 2:
                        wins += 1
                    elif on_team2 and s.winning_team == 1:
                        losses += 1

            self.assertEqual(wins, 1, f"{player.first_name} should have 1 win")
            self.assertEqual(losses, 1, f"{player.first_name} should have 1 loss")
