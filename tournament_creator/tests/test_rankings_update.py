import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model

from tournament_creator.models import Player, RankingsUpdate
from tournament_creator.models.auth import User

class RankingsModelTest(TestCase):
    """Tests for the rankings update history model."""
    
    def test_rankings_update_creation(self):
        """Test creating a RankingsUpdate record."""
        update = RankingsUpdate.objects.create(
            division='O',
            player_count=42,
            successful=True
        )
        self.assertEqual(update.division, 'O')
        self.assertEqual(update.player_count, 42)
        self.assertTrue(update.successful)
        self.assertIsNone(update.updated_by)
        
    def test_rankings_update_string_representation(self):
        """Test the string representation of a RankingsUpdate."""
        update = RankingsUpdate.objects.create(
            division='O',
            player_count=42
        )
        self.assertIn('O Division', str(update))
        self.assertIn(update.timestamp.strftime('%Y-%m-%d'), str(update))


class RankingsViewTest(TestCase):
    """Tests for the rankings view."""
    
    def setUp(self):
        # Create test players
        self.player1 = Player.objects.create(
            first_name="Alice", 
            last_name="Smith", 
            ranking=1, 
            ranking_points=100.0
        )
        self.player2 = Player.objects.create(
            first_name="Bob", 
            last_name="Jones", 
            ranking=2, 
            ranking_points=90.0
        )
        self.player3 = Player.objects.create(
            first_name="Charlie", 
            last_name="Brown", 
            ranking=3, 
            ranking_points=80.0
        )
        
        # Create rankings update record
        self.update = RankingsUpdate.objects.create(
            division='O',
            player_count=3,
            successful=True
        )
        
        # Create test user
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.user.role = 'ADMIN'
        self.user.save()
        
        # Set up client
        self.client = Client()
        self.client.login(username='testuser', password='password123')
    
    def test_rankings_list_view(self):
        """Test the rankings list view."""
        response = self.client.get(reverse('rankings_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tournament_creator/rankings_list.html')
        
        # Check that all players are in the response
        for player in [self.player1, self.player2, self.player3]:
            self.assertContains(response, player.first_name)
            self.assertContains(response, player.last_name)
            
        # Check that rankings update info is in the response
        self.assertContains(response, 'Last updated')
    
    def test_rankings_search(self):
        """Test the search functionality in rankings view."""
        response = self.client.get(reverse('rankings_list'), {'search': 'Alice'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice')
        self.assertNotContains(response, 'Bob')
        self.assertNotContains(response, 'Charlie')
    
    def test_rankings_sorting(self):
        """Test the sorting functionality in rankings view."""
        # Test sorting by first name
        response = self.client.get(reverse('rankings_list'), {
            'sort_by': 'first_name', 
            'sort_order': 'asc'
        })
        self.assertEqual(response.status_code, 200)
        
        # Content should have Alice before Bob before Charlie
        alice_pos = response.content.find(b'Alice')
        bob_pos = response.content.find(b'Bob')
        charlie_pos = response.content.find(b'Charlie')
        self.assertTrue(alice_pos < bob_pos < charlie_pos)
        
        # Test reverse sorting
        response = self.client.get(reverse('rankings_list'), {
            'sort_by': 'first_name', 
            'sort_order': 'desc'
        })
        alice_pos = response.content.find(b'Alice')
        bob_pos = response.content.find(b'Bob')
        charlie_pos = response.content.find(b'Charlie')
        self.assertTrue(charlie_pos < bob_pos < alice_pos)
    
    @patch('tournament_creator.views.rankings_views.call_command')
    def test_update_rankings(self, mock_call_command):
        """Test the update rankings view."""
        response = self.client.post(reverse('update_rankings'), {'division': 'O'})
        self.assertEqual(response.status_code, 302)  # Should redirect
        
        # Check that the command was called
        mock_call_command.assert_called_once_with('update_rankings', division='O')


class RankingsCommandTest(TestCase):
    """Tests for the management command to update rankings."""
    
    @patch('requests.get')
    def test_update_rankings_command(self, mock_get):
        """Test the update_rankings management command."""
        # Mock API responses
        rankings_response = MagicMock()
        rankings_response.json.return_value = [
            {'rank': '1', 'player_id': '123', 'points': '100.0', 'division': 'O'},
            {'rank': '2', 'player_id': '456', 'points': '90.0', 'division': 'O'},
        ]
        
        player_response = MagicMock()
        player_response.json.return_value = [
            {'id': '123', 'name': 'Alice Smith'},
            {'id': '456', 'name': 'Bob Jones'},
        ]
        
        # Configure mock to return these responses
        mock_get.side_effect = [rankings_response, player_response]
        
        # Run the command
        call_command('update_rankings', division='O', dry_run=False)
        
        # Check that players were created
        self.assertEqual(Player.objects.count(), 2)
        self.assertTrue(Player.objects.filter(first_name='Alice', last_name='Smith').exists())
        self.assertTrue(Player.objects.filter(first_name='Bob', last_name='Jones').exists())
        
        # Check that a rankings update record was created
        self.assertEqual(RankingsUpdate.objects.count(), 1)
        update = RankingsUpdate.objects.first()
        self.assertEqual(update.division, 'O')
        self.assertEqual(update.player_count, 2)
        self.assertTrue(update.successful)