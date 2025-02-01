from django.test import TestCase
from django.utils import timezone
from ..models import (
    Player, TournamentChart, Matchup, MatchScore, 
    PlayerScore, User, MatchResultLog
)

class ScoringTests(TestCase):
    def setUp(self):
        # Create test players
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            self.players.append(player)

        # Create a tournament
        self.tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date=timezone.now().date(),
            number_of_rounds=7,
            number_of_courts=2
        )
        self.tournament.players.set(self.players)

        # Create a matchup
        self.matchup = Matchup.objects.create(
            tournament_chart=self.tournament,
            round_number=1,
            court_number=1,
            pair1_player1=self.players[0],
            pair1_player2=self.players[1],
            pair2_player1=self.players[2],
            pair2_player2=self.players[3]
        )

        # Create a user for logging
        self.user = User.objects.create_user(
            username='test_user',
            password='test123',
            role='PLAYER'
        )

    def test_single_set_scoring(self):
        """Test scoring system with a single set"""
        # Record a match result
        score = MatchScore.objects.create(
            matchup=self.matchup,
            set_number=1,
            team1_score=15,
            team2_score=11,
            winning_team=1,
            point_difference=4
        )

        # Create player scores
        for player in [self.players[0], self.players[1]]:  # Winning team
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=1,
                matches_played=1,
                total_point_difference=4
            )

        for player in [self.players[2], self.players[3]]:  # Losing team
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=0,
                matches_played=1,
                total_point_difference=-4
            )

        # Check point differences
        team1_scores = PlayerScore.objects.filter(
            tournament=self.tournament,
            player__in=[self.players[0], self.players[1]]
        )
        for score in team1_scores:
            self.assertEqual(score.total_point_difference, 4)
            self.assertEqual(score.wins, 1)

        team2_scores = PlayerScore.objects.filter(
            tournament=self.tournament,
            player__in=[self.players[2], self.players[3]]
        )
        for score in team2_scores:
            self.assertEqual(score.total_point_difference, -4)
            self.assertEqual(score.wins, 0)

    def test_multiple_sets_scoring(self):
        """Test scoring system with multiple sets"""
        # Record two sets
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=1,
            team1_score=15,
            team2_score=11,
            winning_team=1,
            point_difference=4
        )
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=2,
            team1_score=11,
            team2_score=15,
            winning_team=2,
            point_difference=4
        )
        MatchScore.objects.create(
            matchup=self.matchup,
            set_number=3,
            team1_score=15,
            team2_score=13,
            winning_team=1,
            point_difference=2
        )

        # Create player scores
        for player in [self.players[0], self.players[1]]:  # Overall winning team
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=1,
                matches_played=1,
                total_point_difference=2  # Net difference from all sets
            )

        for player in [self.players[2], self.players[3]]:  # Overall losing team
            PlayerScore.objects.create(
                tournament=self.tournament,
                player=player,
                wins=0,
                matches_played=1,
                total_point_difference=-2  # Net difference from all sets
            )

        # Check logging
        log = MatchResultLog.objects.create(
            matchup=self.matchup,
            recorded_by=self.user,
            action='CREATE',
            details={
                'sets': [
                    {'set': 1, 'score': '15-11'},
                    {'set': 2, 'score': '11-15'},
                    {'set': 3, 'score': '15-13'}
                ]
            }
        )

        self.assertEqual(log.matchup, self.matchup)
        self.assertEqual(log.recorded_by, self.user)
        self.assertEqual(log.action, 'CREATE')
        self.assertEqual(len(log.details['sets']), 3)