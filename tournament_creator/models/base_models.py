from django.db import models

class Player(models.Model):
    """Represents a player registered in the system."""
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    ranking = models.IntegerField()
    ranking_points = models.FloatField(default=0)
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    class Meta:
        ordering = ['ranking']

class Pair(models.Model):
    """Represents a fixed pair (team) of two players."""
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair_player1')
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair_player2')
    ranking_points_sum = models.FloatField()
    seed = models.IntegerField(null=True, blank=True)
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
    date = models.DateField()
    number_of_rounds = models.IntegerField()
    number_of_courts = models.IntegerField()
    # Consider relation by pairs or by players based on tournament type
    players = models.ManyToManyField(Player, through='TournamentPlayer', blank=True)
    pairs = models.ManyToManyField(Pair, through='TournamentPair', blank=True)
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
        ordering = ['round_number', 'court_number']

class TournamentArchetype(models.Model):
    """Abstract base for tournament formats."""
    TOURNAMENT_TYPES = (
        ('PAIRS', 'Pairs'),
        ('MOC', 'Monarch of the Court'),
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tournament_category = models.CharField(max_length=12, choices=TOURNAMENT_TYPES, default='PAIRS')
    def __str__(self):
        return self.name
    def create_tournament(self, players_or_pairs):
        # Tournament logic is delegated to concrete archetypes that know
        # if they're using pairs or players
        raise NotImplementedError()
    def calculate_rounds(self, num_entrants: int) -> int:
        """Concrete archetypes must override."""
        raise NotImplementedError()
    def calculate_courts(self, num_entrants: int) -> int:
        raise NotImplementedError()
    def generate_matchups(self, tournament_chart, players_or_pairs):
        raise NotImplementedError()
