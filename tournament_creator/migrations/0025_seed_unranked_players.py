from django.db import migrations

# Players not yet in the doubledisccourt rankings, seeded so they can claim a
# login account at /signup/. A sentinel ranking sorts them last; when they later
# appear in the rankings feed, update_rankings matches them by normalized name
# and fills in real ranking/points in place (see the command's name_key match).
SEED_PLAYERS = [
    ("Riku", "Aro"),
    ("Markus", "Nora"),
    ("Miiro", "Tähti"),
    ("Petri", "Mäkinen"),
]

SENTINEL_RANKING = 9999


def add_players(apps, schema_editor):
    Player = apps.get_model('tournament_creator', 'Player')
    for first_name, last_name in SEED_PLAYERS:
        Player.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
            defaults={'ranking': SENTINEL_RANKING, 'ranking_points': 0},
        )


def remove_players(apps, schema_editor):
    Player = apps.get_model('tournament_creator', 'Player')
    for first_name, last_name in SEED_PLAYERS:
        # Only remove if still an unclaimed sentinel row (never touched by a
        # rankings update and not linked to an account).
        Player.objects.filter(
            first_name=first_name,
            last_name=last_name,
            ranking=SENTINEL_RANKING,
            user__isnull=True,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0024_player_user'),
    ]

    operations = [
        migrations.RunPython(add_players, remove_players),
    ]
