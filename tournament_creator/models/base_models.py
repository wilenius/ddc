from django.db import models

class Player(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    ranking = models.IntegerField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['ranking']

class TournamentChart(models.Model):
    name = models.CharField(max_length=255, default="Unnamed Tournament")
    date = models.DateField()
    players = models.ManyToManyField(Player, through='TournamentPlayer')
    number_of_rounds = models.IntegerField()
    number_of_courts = models.IntegerField()

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-date']

class TournamentPlayer(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        ordering = ['player__ranking']

class Matchup(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE, related_name='matchups')
    pair1_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player1_matchups')
    pair1_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player2_matchups')
    pair2_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player1_matchups')
    pair2_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player2_matchups')
    round_number = models.IntegerField()
    court_number = models.IntegerField()

    def __str__(self):
        return f"Round {self.round_number}, Court {self.court_number}"

    class Meta:
        ordering = ['round_number', 'court_number']

class TournamentArchetype(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def create_tournament(self, players):
        tournament_chart = TournamentChart.objects.create(
            number_of_rounds=self.calculate_rounds(len(players)),
            number_of_courts=self.calculate_courts(len(players)),
        )
        tournament_chart.players.set(players)
        self.generate_matchups(tournament_chart, players)
        return tournament_chart

    def calculate_rounds(self, num_players):
        return 6  # Default value

    def calculate_courts(self, num_players):
        return 1  # Default value

    def generate_matchups(self, tournament_chart, players):
        pass  # To be implemented by subclasses