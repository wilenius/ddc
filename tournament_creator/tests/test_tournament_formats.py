from django.test import TestCase
from django.db import models
from ..models import Player, TournamentChart, Matchup
from ..models.tournament_types import (
    MonarchOfTheCourt5, MonarchOfTheCourt6, MonarchOfTheCourt7,
    MonarchOfTheCourt8, MonarchOfTheCourt9, MonarchOfTheCourt10,
    MonarchOfTheCourt11, MonarchOfTheCourt12, MonarchOfTheCourt13,
    MonarchOfTheCourt14, MonarchOfTheCourt15, MonarchOfTheCourt16
)

class TournamentFormatsTest(TestCase):
    """
    Tests for the different tournament formats.
    """
    
    def test_generate_5_player_tournament(self):
        """Test generation of 5-player tournament format"""
        # Create 5 players
        players = []
        for i in range(5):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            players.append(player)
        
        tournament_type = MonarchOfTheCourt5()
        
        # Create tournament chart
        tournament = TournamentChart.objects.create(
            name='Test 5-player Tournament',
            date='2025-01-01',
            number_of_rounds=tournament_type.calculate_rounds(5),
            number_of_courts=tournament_type.calculate_courts(5)
        )
        tournament.players.set(players)
        
        tournament_type.generate_matchups(tournament, players)
        
        # Check total number of matchups (5 rounds × 1 court per round)
        self.assertEqual(Matchup.objects.filter(tournament_chart=tournament).count(), 5)
        
        # Check rounds
        rounds = Matchup.objects.filter(tournament_chart=tournament).values_list(
            'round_number', flat=True).distinct().order_by('round_number')
        self.assertEqual(list(rounds), [1, 2, 3, 4, 5])
        
        # Check courts per round
        for round_num in range(1, 6):
            court_count = Matchup.objects.filter(
                tournament_chart=tournament,
                round_number=round_num
            ).count()
            self.assertEqual(court_count, 1)
            
        # Each player should play in 4 matches 
        # (with 5 players, each player sits out one round)
        for player in players:
            match_count = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) |
                models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) |
                models.Q(pair2_player2=player)
            ).count()
            self.assertEqual(match_count, 4)
            
    def test_generate_6_player_tournament(self):
        """Test generation of 6-player tournament format"""
        # Create 6 players
        players = []
        for i in range(6):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            players.append(player)
        
        tournament_type = MonarchOfTheCourt6()
        
        # Create tournament chart
        tournament = TournamentChart.objects.create(
            name='Test 6-player Tournament',
            date='2025-01-01',
            number_of_rounds=tournament_type.calculate_rounds(6),
            number_of_courts=tournament_type.calculate_courts(6)
        )
        tournament.players.set(players)
        
        tournament_type.generate_matchups(tournament, players)
        
        # Check total number of matchups
        self.assertEqual(Matchup.objects.filter(tournament_chart=tournament).count(), 7)
        
        # Each player should play in 7*4/6 ≈ 4.67 matches rounded to 4 or 5
        for player in players:
            match_count = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) |
                models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) |
                models.Q(pair2_player2=player)
            ).count()
            self.assertIn(match_count, [4, 5])
            
    def test_generate_16_player_tournament(self):
        """Test generation of 16-player tournament format with 4 courts"""
        # Create 16 players
        players = []
        for i in range(16):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            players.append(player)
        
        tournament_type = MonarchOfTheCourt16()
        
        # Create tournament chart
        tournament = TournamentChart.objects.create(
            name='Test 16-player Tournament',
            date='2025-01-01',
            number_of_rounds=tournament_type.calculate_rounds(16),
            number_of_courts=tournament_type.calculate_courts(16)
        )
        tournament.players.set(players)
        
        tournament_type.generate_matchups(tournament, players)
        
        # Check total number of matchups
        matchups = Matchup.objects.filter(tournament_chart=tournament)
        self.assertGreater(matchups.count(), 0)
        
        # Check courts count
        courts = Matchup.objects.filter(tournament_chart=tournament).values_list(
            'court_number', flat=True).distinct().order_by('court_number')
        self.assertEqual(list(courts), [1, 2, 3, 4])
        
        # Each player should have at least 8 matches
        for player in players:
            match_count = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) |
                models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) |
                models.Q(pair2_player2=player)
            ).count()
            self.assertGreaterEqual(match_count, 8)
    
    def test_player_count_validation(self):
        """Test that tournament formats reject wrong player counts"""
        # Create 7 players but try to use them for 6-player format
        players = []
        for i in range(7):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            players.append(player)
        
        tournament_type = MonarchOfTheCourt6()
        
        # Create tournament chart
        tournament = TournamentChart.objects.create(
            name='Test Invalid Tournament',
            date='2025-01-01',
            number_of_rounds=tournament_type.calculate_rounds(6),
            number_of_courts=tournament_type.calculate_courts(6)
        )
        tournament.players.set(players)
        
        # This should raise a ValueError
        with self.assertRaises(ValueError):
            tournament_type.generate_matchups(tournament, players)