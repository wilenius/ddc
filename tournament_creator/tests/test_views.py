from django.test import TestCase, Client
from django.urls import reverse
from ..models import Player, TournamentChart, TournamentArchetype, User, Matchup
from django.utils import timezone

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create users
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

        # Create test data
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            self.players.append(player)

        self.archetype = TournamentArchetype.objects.create(
            name="Cade Loving's 8-player KoC",
            description='Test tournament type'
        )

        self.tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)

    def test_tournament_list_view(self):
        """Test tournament list view access"""
        url = reverse('tournament_list')
        
        # Unauthenticated user should be redirected to login
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Authenticated users should have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Tournament')

    def test_tournament_create_permissions(self):
        """Test tournament creation permissions"""
        url = reverse('tournament_create')
        data = {
            'name': 'New Tournament',
            'date': timezone.now().date(),
            'archetype': self.archetype.id,
            'players': [player.id for player in self.players[:8]]
        }

        # Spectator should not have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)

        # Player should have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_record_match_result_permissions(self):
        """Test match result recording permissions"""
        # Create a matchup
        matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[1],
            pair2_player1=self.players[2],
            pair2_player2=self.players[3]
        )

        url = reverse('record_match_result', kwargs={
            'tournament_id': self.tournament.id,
            'matchup_id': matchup.id
        })

        data = {
            'team1_scores': '[15]',
            'team2_scores': '[11]',
            'winning_team': '1'
        }

        # Spectator should not have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403)

        # Player should have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_tournament_delete_permissions(self):
        """Test tournament deletion permissions"""
        url = reverse('tournament_delete', kwargs={'pk': self.tournament.pk})
        
        # Unauthenticated user should be redirected to login
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        # Spectator should not have access
        self.client.login(username='spectator_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        
        # Player should not have access
        self.client.login(username='player_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        
        # Admin should have access
        self.client.login(username='admin_test', password='test123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        
        # Verify tournament was deleted
        self.assertFalse(TournamentChart.objects.filter(pk=self.tournament.pk).exists())