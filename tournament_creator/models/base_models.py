from django.db import models

class Player(models.Model):
    """Represents a player registered in the system."""
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    ranking = models.IntegerField()
    ranking_points = models.FloatField(default=0)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_display_name(self, players=None):
        """
        Returns a name for display with first name and enough of the last name to disambiguate.
        If 'players' is provided, checks for duplicate first names and adds last name initial(s).
        """
        # If no players list is provided or just one player, return first name
        if not players or len(players) <= 1:
            return self.first_name

        # Find players with the same first name
        same_first_name = [p for p in players if p.first_name == self.first_name and p.id != self.id]

        # If no duplicate first names, return just first name
        if not same_first_name:
            return self.first_name

        # Find minimum length of last name needed for disambiguation
        for i in range(1, len(self.last_name) + 1):
            my_surname_prefix = self.last_name[:i]
            # Check if this prefix is unique among players with same first name
            if not any(p.last_name.startswith(my_surname_prefix) for p in same_first_name):
                return f"{self.first_name} {my_surname_prefix}."

        # If we need the full last name for disambiguation
        return f"{self.first_name} {self.last_name}"

    def get_display_name_last_name_mode(self, players=None):
        """
        Returns a name for display with last name and first name initial(s) for disambiguation.
        If 'players' is provided, checks for duplicate last names and adds first name initial(s).
        """
        # If no players list is provided or just one player, return last name
        if not players or len(players) <= 1:
            return self.last_name

        # Find players with the same last name
        same_last_name = [p for p in players if p.last_name == self.last_name and p.id != self.id]

        # If no duplicate last names, return just last name
        if not same_last_name:
            return self.last_name

        # Find minimum length of first name needed for disambiguation
        for i in range(1, len(self.first_name) + 1):
            my_first_name_prefix = self.first_name[:i]
            # Check if this prefix is unique among players with same last name
            if not any(p.first_name.startswith(my_first_name_prefix) for p in same_last_name):
                return f"{my_first_name_prefix}. {self.last_name}"

        # If we need the full first name for disambiguation
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['ranking']

class Pair(models.Model):
    """Represents a fixed pair (team) of two players."""
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair_player1')
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair_player2')
    ranking_points_sum = models.FloatField()
    seed = models.IntegerField(null=True, blank=True)
    entry_order = models.IntegerField(null=True, blank=True, help_text="Order in which this pair was entered (1-based)")
    def calculate_points_sum(self):
        return self.player1.ranking_points + self.player2.ranking_points
    def save(self, *args, **kwargs):
        self.ranking_points_sum = self.calculate_points_sum()
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.player1} & {self.player2}"

class TournamentChart(models.Model):
    """Model storing tournament-level information, including participants and structure."""
    name = models.CharField(max_length=255, default="Unnamed Tournament")
    date = models.DateField()  # Start date (kept for backward compatibility)
    end_date = models.DateField(null=True, blank=True, help_text="End date for multi-day tournaments. Leave blank for single-day tournaments.")
    number_of_rounds = models.IntegerField()
    number_of_courts = models.IntegerField()
    number_of_stages = models.IntegerField(default=1, help_text="Number of stages in this tournament (1 for single-stage, 2+ for multi-stage)")
    archetype = models.ForeignKey('TournamentArchetype', on_delete=models.SET_NULL, null=True, blank=True, related_name='tournaments')
    # Consider relation by pairs or by players based on tournament type
    players = models.ManyToManyField(Player, through='TournamentPlayer', blank=True)
    pairs = models.ManyToManyField(Pair, through='TournamentPair', blank=True)
    notify_by_email = models.BooleanField(default=False)
    notify_by_signal = models.BooleanField(default=False)
    notify_by_matrix = models.BooleanField(default=False)
    # Per-tournament Signal notification recipients (optional, falls back to global settings)
    signal_recipient_usernames = models.TextField(blank=True, help_text="Comma-separated phone numbers (e.g., +358401234567, +358409876543). Leave empty to use global settings.")
    signal_recipient_group_ids = models.TextField(blank=True, help_text="Comma-separated group IDs (e.g., group.ABC123==). Leave empty to use global settings.")
    # Name display preference
    NAME_DISPLAY_CHOICES = [
        ('FIRST', 'First names'),
        ('LAST', 'Last names'),
    ]
    name_display_format = models.CharField(max_length=10, choices=NAME_DISPLAY_CHOICES, default='FIRST', help_text="How to display player names in notifications and tournament view")
    show_structure = models.BooleanField(default=False, help_text="Show tournament structure in a separate block")
    def __str__(self):
        return self.name
    class Meta:
        ordering = ['-date']

class TournamentPlayer(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    class Meta:
        ordering = ['player__ranking']

class TournamentPair(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    pair = models.ForeignKey(Pair, on_delete=models.CASCADE)
    seed = models.IntegerField(null=True, blank=True)

class Stage(models.Model):
    """
    Represents a stage within a tournament (e.g., Pool Play Stage 1, Pool Play Stage 2, Finals).
    Allows for multi-stage tournaments with different structures and scoring approaches.
    """
    STAGE_TYPE_CHOICES = [
        ('POOL', 'Pool Play'),
        ('PLAYOFF', 'Playoff/Finals'),
        ('ROUND_ROBIN', 'Round Robin'),
    ]

    SCORING_MODE_CHOICES = [
        ('CUMULATIVE', 'Cumulative - Scores carry over from previous stages'),
        ('RESET', 'Reset - Scores start fresh for this stage'),
    ]

    tournament = models.ForeignKey(TournamentChart, on_delete=models.CASCADE, related_name='stages')
    stage_number = models.IntegerField(help_text="Order of this stage (1-based)")
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPE_CHOICES, default='POOL')
    name = models.CharField(max_length=100, help_text="Display name for this stage (e.g., 'Stage 1', 'Pool A', 'Finals')")
    scoring_mode = models.CharField(max_length=20, choices=SCORING_MODE_CHOICES, default='CUMULATIVE')

    class Meta:
        ordering = ['tournament', 'stage_number']
        unique_together = ['tournament', 'stage_number']

    def __str__(self):
        return f"{self.tournament.name} - {self.name}"

def pair_or_player_str(obj):
    if hasattr(obj, 'pair1') and hasattr(obj, 'pair2'):
        return f"{obj.pair1} vs {obj.pair2}"
    elif hasattr(obj, 'pair1_player1'):
        return f"{obj.pair1_player1} & {obj.pair1_player2} vs {obj.pair2_player1} & {obj.pair2_player2}"
    return str(obj)

class Matchup(models.Model):
    """
    A specific match. For Pairs tournaments: use pair1/pair2.
    For MoC: use player fields. At most fields for one purpose for a given tournament.
    """
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE, related_name='matchups')
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='matchups', null=True, blank=True)
    # Fields for pairs tournaments
    pair1 = models.ForeignKey(Pair, on_delete=models.CASCADE, related_name='as_pair1', null=True, blank=True)
    pair2 = models.ForeignKey(Pair, on_delete=models.CASCADE, related_name='as_pair2', null=True, blank=True)
    # Fields for MoC tournaments
    pair1_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player1_matchups', null=True, blank=True)
    pair1_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player2_matchups', null=True, blank=True)
    pair2_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player1_matchups', null=True, blank=True)
    pair2_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player2_matchups', null=True, blank=True)
    round_number = models.IntegerField()
    court_number = models.IntegerField()
    def __str__(self):
        return pair_or_player_str(self)
    class Meta:
        ordering = ['stage__stage_number', 'round_number', 'court_number']

class TournamentArchetype(models.Model):
    """Base for tournament formats stored in the database."""
    TOURNAMENT_TYPES = (
        ('PAIRS', 'Pairs'),
        ('MOC', 'Monarch of the Court'),
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tournament_category = models.CharField(max_length=12, choices=TOURNAMENT_TYPES, default='PAIRS')
    notes = models.TextField(blank=True, help_text="Explain the tournament structure and idiosyncrasies")
    
    def __str__(self):
        return self.name
    
    @property
    def player_count(self):
        """Extract the number of players/pairs from the tournament name for sorting."""
        import re
        # Look for numbers at the start of the name (e.g., "5-player", "4 pairs")
        match = re.search(r'^(\d+)', self.name)
        if match:
            return int(match.group(1))
        return 999  # Put tournaments without numbers at the end
    
    class Meta:
        ordering = ['tournament_category', 'name']
        
    def create_tournament(self, players_or_pairs):
        """Create a tournament with the given players or pairs."""
        # We can either implement this method or simply call
        # calculate_rounds, calculate_courts, and generate_matchups instead
        # For now, we raise an error since this method might not be needed
        raise NotImplementedError("Use calculate_rounds, calculate_courts, and generate_matchups instead")
        
    def calculate_rounds(self, num_entrants: int) -> int:
        """Calculate the number of rounds needed for the tournament."""
        # Direct implementation based on tournament type
        if self.tournament_category == 'PAIRS':
            return num_entrants - 1
        
        # MoC Tournament formats
        if self.tournament_category == 'MOC':
            # Check player count for each format
            if "5-player" in self.name:
                if num_entrants != 5:
                    raise ValueError("This tournament type requires exactly 5 players")
                return 5
                
            elif "6-player" in self.name:
                if num_entrants != 6:
                    raise ValueError("This tournament type requires exactly 6 players")
                return 7
                
            elif "7-player" in self.name:
                if num_entrants != 7:
                    raise ValueError("This tournament type requires exactly 7 players")
                return 10
                
            elif "8-player" in self.name:
                if num_entrants != 8:
                    raise ValueError("This tournament type requires exactly 8 players")
                return 7
                
            elif "9-player" in self.name:
                if num_entrants != 9:
                    raise ValueError("This tournament type requires exactly 9 players")
                return 10
                
            elif "10-player" in self.name:
                if num_entrants != 10:
                    raise ValueError("This tournament type requires exactly 10 players")
                return 11
                
            elif "11-player" in self.name:
                if num_entrants != 11:
                    raise ValueError("This tournament type requires exactly 11 players")
                return 14
                
            elif "12-player" in self.name:
                if num_entrants != 12:
                    raise ValueError("This tournament type requires exactly 12 players")
                return 12
                
            elif "13-player" in self.name:
                if num_entrants != 13:
                    raise ValueError("This tournament type requires exactly 13 players")
                return 13
                
            elif "14-player" in self.name:
                if num_entrants != 14:
                    raise ValueError("This tournament type requires exactly 14 players")
                return 15
                
            elif "15-player" in self.name:
                if num_entrants != 15:
                    raise ValueError("This tournament type requires exactly 15 players")
                return 18
                
            elif "16-player" in self.name:
                if num_entrants != 16:
                    raise ValueError("This tournament type requires exactly 16 players")
                return 17
            
        # Default fallback - should not reach here for known tournament types
        raise NotImplementedError(f"calculate_rounds not implemented for {self.name}")
        
    def calculate_courts(self, num_entrants: int) -> int:
        """Calculate the number of courts needed for the tournament."""
        # For pairs tournaments
        if self.tournament_category == 'PAIRS':
            return min(num_entrants, 4)
            
        # For MoC tournaments
        if self.tournament_category == 'MOC':
            if "5-player" in self.name or "6-player" in self.name or "7-player" in self.name:
                return 1
            elif "8-player" in self.name or "9-player" in self.name or "10-player" in self.name or "11-player" in self.name:
                return 2
            elif "12-player" in self.name or "13-player" in self.name or "14-player" in self.name or "15-player" in self.name:
                return 3
            elif "16-player" in self.name:
                return 4
            
        # Default fallback
        raise NotImplementedError(f"calculate_courts not implemented for {self.name}")
        
    def generate_matchups(self, tournament_chart, players_or_pairs):
        """Generate matchups for the tournament."""
        # For Monarch of the Court tournaments
        if self.tournament_category == 'MOC':
            # Redirect to appropriate implementation in tournament_types.py
            from .tournament_types import get_implementation
            implementation = get_implementation(self)
            if implementation:
                return implementation.generate_matchups(tournament_chart, players_or_pairs)
                
            # Fallback for 8-player format (for backward compatibility)
            if "8-player" in self.name:
                players = players_or_pairs
                if len(players) != 8:
                    raise ValueError("This tournament type requires exactly 8 players")
                    
                # Sort players by ranking
                sorted_players = sorted(players, key=lambda p: p.ranking if p.ranking is not None else 9999)
                if len(sorted_players) < 8:
                    raise ValueError(f"This tournament type requires exactly 8 players, got {len(sorted_players)}")
                
                # Create all matchups for Cade Loving's 8-player tournament
                # The format has 7 rounds with 2 courts per round
                # Each matchup has 2 players vs 2 players
                # We'll use the players array sorted by ranking (index 0 = rank 1)
                
                # Round 1
                # Court 1: 1&3 vs 6&8 (Power Rank: 4 v 14)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[2],  # Player 3
                    pair2_player1=sorted_players[5],  # Player 6
                    pair2_player2=sorted_players[7],  # Player 8
                    round_number=1,
                    court_number=1
                )
                # Court 2: 2&4 vs 5&7 (Power Rank: 6 v 12)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[1],  # Player 2
                    pair1_player2=sorted_players[3],  # Player 4
                    pair2_player1=sorted_players[4],  # Player 5
                    pair2_player2=sorted_players[6],  # Player 7
                    round_number=1,
                    court_number=2
                )
                
                # Round 2
                # Court 1: 1&6 vs 4&7 (Power Rank: 7 v 11)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[5],  # Player 6
                    pair2_player1=sorted_players[3],  # Player 4
                    pair2_player2=sorted_players[6],  # Player 7
                    round_number=2,
                    court_number=1
                )
                # Court 2: 3&8 vs 2&5 (Power Rank: 11 v 7)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[2],  # Player 3
                    pair1_player2=sorted_players[7],  # Player 8
                    pair2_player1=sorted_players[1],  # Player 2
                    pair2_player2=sorted_players[4],  # Player 5
                    round_number=2,
                    court_number=2
                )
                
                # Round 3
                # Court 1: 1&2 vs 7&8 (Power Rank: 3 v 15)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[1],  # Player 2
                    pair2_player1=sorted_players[6],  # Player 7
                    pair2_player2=sorted_players[7],  # Player 8
                    round_number=3,
                    court_number=1
                )
                # Court 2: 3&4 vs 5&6 (Power Rank: 7 v 11)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[2],  # Player 3
                    pair1_player2=sorted_players[3],  # Player 4
                    pair2_player1=sorted_players[4],  # Player 5
                    pair2_player2=sorted_players[5],  # Player 6
                    round_number=3,
                    court_number=2
                )
                
                # Round 4
                # Court 1: 1&5 vs 2&6 (Power Rank: 6 v 8)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[4],  # Player 5
                    pair2_player1=sorted_players[1],  # Player 2
                    pair2_player2=sorted_players[5],  # Player 6
                    round_number=4,
                    court_number=1
                )
                # Court 2: 4&8 vs 3&7 (Power Rank: 12 v 10)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[3],  # Player 4
                    pair1_player2=sorted_players[7],  # Player 8
                    pair2_player1=sorted_players[2],  # Player 3
                    pair2_player2=sorted_players[6],  # Player 7
                    round_number=4,
                    court_number=2
                )
                
                # Round 5
                # Court 1: 1&8 vs 4&5 (Power Rank: 9 v 9)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[7],  # Player 8
                    pair2_player1=sorted_players[3],  # Player 4
                    pair2_player2=sorted_players[4],  # Player 5
                    round_number=5,
                    court_number=1
                )
                # Court 2: 2&7 vs 3&6 (Power Rank: 9 v 9)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[1],  # Player 2
                    pair1_player2=sorted_players[6],  # Player 7
                    pair2_player1=sorted_players[2],  # Player 3
                    pair2_player2=sorted_players[5],  # Player 6
                    round_number=5,
                    court_number=2
                )
                
                # Round 6
                # Court 1: 1&7 vs 3&5 (Power Rank: 8 v 8)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[6],  # Player 7
                    pair2_player1=sorted_players[2],  # Player 3
                    pair2_player2=sorted_players[4],  # Player 5
                    round_number=6,
                    court_number=1
                )
                # Court 2: 4&6 vs 2&8 (Power Rank: 10 v 10)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[3],  # Player 4
                    pair1_player2=sorted_players[5],  # Player 6
                    pair2_player1=sorted_players[1],  # Player 2
                    pair2_player2=sorted_players[7],  # Player 8
                    round_number=6,
                    court_number=2
                )
                
                # Round 7
                # Court 1: 1&4 vs 2&3 (Power Rank: 5 v 5)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[0],  # Player 1
                    pair1_player2=sorted_players[3],  # Player 4
                    pair2_player1=sorted_players[1],  # Player 2
                    pair2_player2=sorted_players[2],  # Player 3
                    round_number=7,
                    court_number=1
                )
                # Court 2: 6&7 vs 5&8 (Power Rank: 13 v 13)
                Matchup.objects.create(
                    tournament_chart=tournament_chart,
                    pair1_player1=sorted_players[5],  # Player 6
                    pair1_player2=sorted_players[6],  # Player 7
                    pair2_player1=sorted_players[4],  # Player 5
                    pair2_player2=sorted_players[7],  # Player 8
                    round_number=7,
                    court_number=2
                )
                return
        
        # For pairs tournaments
        if self.tournament_category == 'PAIRS':
            # Pairs implementation would go here
            raise NotImplementedError("Pairs tournament matchup generation not yet implemented")
            
        # Default fallback
        raise NotImplementedError(f"generate_matchups not implemented for {self.name}")
