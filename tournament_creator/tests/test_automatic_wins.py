from django.test import TestCase
from django.utils import timezone
from ..models import Player, TournamentChart, TournamentArchetype
from ..models.tournament_types import MonarchOfTheCourt11, get_implementation
from ..models.scoring import PlayerScore


class AutomaticWinsTests(TestCase):
    """Tests for automatic wins functionality in MoC tournaments."""

    def setUp(self):
        """Set up test data."""
        # Create 11 players
        self.players = []
        for i in range(11):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test{i+1}',
                ranking=i+1
            )
            self.players.append(player)

        # Create tournament without archetype for simpler testing
        self.tournament = TournamentChart.objects.create(
            name='Test 11-Player MoC',
            date=timezone.now().date(),
            number_of_rounds=14,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)

    def test_automatic_wins_defined(self):
        """Test that MonarchOfTheCourt11 defines automatic wins."""
        moc11 = MonarchOfTheCourt11()
        auto_wins = moc11.get_automatic_wins(11)

        # Seeds 1 & 2 (indices 0 & 1) should get 1 automatic win
        self.assertEqual(auto_wins.get(0), 1, "Seed 1 should get 1 automatic win")
        self.assertEqual(auto_wins.get(1), 1, "Seed 2 should get 1 automatic win")

        # Other seeds should not have automatic wins
        for seed in range(2, 11):
            self.assertIsNone(auto_wins.get(seed), f"Seed {seed+1} should not have automatic wins")

    def test_get_implementation(self):
        """Test that get_implementation returns the correct class for 11-player MoC."""
        # Get the 11-player MoC archetype from migrations
        try:
            archetype_db = TournamentArchetype.objects.get(name="11-player Monarch of the Court")
            impl = get_implementation(archetype_db)
            self.assertIsInstance(impl, MonarchOfTheCourt11)
            self.assertTrue(hasattr(impl, 'get_automatic_wins'))
        except TournamentArchetype.DoesNotExist:
            self.skipTest("11-player MoC archetype not found in database")

    def test_player_score_has_automatic_wins_field(self):
        """Test that PlayerScore model has automatic_wins field."""
        score = PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[0],
            wins=5,
            matches_played=10,
            automatic_wins=1
        )

        self.assertEqual(score.automatic_wins, 1)

        # Test that default is 0
        score2 = PlayerScore.objects.create(
            tournament=self.tournament,
            player=self.players[1],
            wins=5,
            matches_played=10
        )
        self.assertEqual(score2.automatic_wins, 0)
