from django.db import models

# player model

class Player(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)   

    ranking = models.IntegerField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# tournament model

class TournamentChart(models.Model):
    players = models.ManyToManyField(Player, through='TournamentPlayer')
    number_of_rounds = models.IntegerField()
    number_of_courts = models.IntegerField()

    def __str__(self):
        return f"Tournament Chart with {self.players.count()} players"

class TournamentPlayer(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        ordering = ['player__ranking']  # Order by player ranking

class Matchup(models.Model):
    tournament_chart = models.ForeignKey(TournamentChart, on_delete=models.CASCADE, related_name='matchups')
    pair1_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player1_matchups')
    pair1_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair1_player2_matchups', blank=True, null=True)
    pair2_player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player1_matchups')
    pair2_player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pair2_player2_matchups', blank=True, null=True)
    round_number = models.IntegerField()
    court_number = models.IntegerField()
    # needs group number too
    # courts need separate model? in addition to number, location? for multi-location tournaments?

    def __str__(self):
        return f"Round {self.round_number}, Court {self.court_number}"

class TournamentArchetype(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Add any other common archetype fields here (e.g., game type, scoring system)

    def __str__(self):
        return self.name

    def create_tournament(self, players):
        """
        Creates a TournamentChart instance based on this archetype and the given players.
        """
        tournament_chart = TournamentChart.objects.create(
            number_of_rounds=self.calculate_rounds(len(players)),
            number_of_courts=self.calculate_courts(len(players)),
        )
        tournament_chart.players.set(players)  # Add players to the tournament

        # Generate matchups based on the archetype's rules
        self.generate_matchups(tournament_chart, players) 

        return tournament_chart

    def calculate_rounds(self, num_players):
        """
        Calculates the number of rounds based on the number of players and archetype rules.
        """
        # Implement archetype-specific logic here
        # Example for "Cade Loving King of the Court":
        if num_players == 5:
            return 4 
        else:
            # Add logic for other player counts or raise an error
            pass 

    def calculate_courts(self, num_players):
        """
        Calculates the number of courts needed based on the archetype and players.
        """
        # Implement archetype-specific logic here
        return 1  # Example: Always 1 court for "Cade Loving King of the Court"

    def generate_matchups(self, tournament_chart, players):
        """
        Generates matchups for the tournament based on archetype rules.
        """
        # Implement archetype-specific logic here
        if self.name == "Cade Loving King of the Court" and len(players) == 5:
            # Example matchup generation for 5 players:
            # Round 1
            Matchup.objects.create(
                tournament_chart=tournament_chart,
                pair1_player1=players[0],  # Rank 1
                pair1_player2=players[1],  # Rank 2
                pair2_player1=players[2],  # Rank 3
                pair2_player2=players[4],  # Rank 5
                round_number=1,
                court_number=1,
            )
            # ... add other matchups for round 1, 2, 3, etc.
        else:
            # Add logic for other archetypes or raise an error
            pass


class CadeLovingKingOfTheCourt(TournamentArchetype):
    """
    A concrete archetype for "Cade Loving King of the Court" with 5 players.
    """
    class Meta:
        proxy = True  # This makes it a proxy model

    def generate_matchups(self, tournament_chart, players):
        """
        Generates the specific matchups for "Cade Loving King of the Court".
        """
        # Implement the exact matchup logic for this archetype
        # ... (add all the matchups for all rounds as shown in the example above)
    # tournament archetypes to a separate model file?

