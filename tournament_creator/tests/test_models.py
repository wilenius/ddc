from django.test import TestCase
from ..models import Player, TournamentChart, TournamentArchetype, User
from django.utils import timezone

class ModelTests(TestCase):
    def setUp(self):
        # Create test users with different roles
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='test123',
            role='ADMIN'
        )
        self.player_user = User.objects.create_user(
            username='player_test',
            password='test123',
            role='PLAYER'
        )
        self.spectator_user = User.objects.create_user(
            username='spectator_test',
            password='test123',
            role='SPECTATOR'
        )

        # Create test players
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            self.players.append(player)

        # Create tournament archetype
        self.archetype = TournamentArchetype.objects.create(
            name="Test KoC",
            description='Test tournament type'
        )

    def test_player_creation(self):
        """Test that players are created with correct attributes"""
        player = self.players[0]
        self.assertEqual(player.first_name, 'Player1')
        self.assertEqual(player.ranking, 1)
        self.assertEqual(str(player), 'Player1 Test')

    def test_tournament_creation(self):
        """Test tournament creation with players"""
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)

        self.assertEqual(tournament.players.count(), 8)
        self.assertEqual(tournament.name, 'Test Tournament')
        self.assertEqual(tournament.number_of_courts, 2)

    def test_user_roles(self):
        """Test user role methods"""
        self.assertTrue(self.admin_user.is_admin())
        self.assertTrue(self.player_user.is_player())
        self.assertTrue(self.spectator_user.is_spectator())
        
        self.assertFalse(self.admin_user.is_player())
        self.assertFalse(self.player_user.is_admin())
        self.assertFalse(self.spectator_user.is_admin())