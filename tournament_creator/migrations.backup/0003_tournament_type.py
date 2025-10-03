from django.db import migrations

def create_tournament_type(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    TournamentArchetype.objects.create(
        name="Cade Loving's 8-player KoC",
        description='A 7-round tournament format for 8 players with pre-determined matchups, played on 2 courts.'
    )

def remove_tournament_type(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    TournamentArchetype.objects.filter(name="Cade Loving's 8-player KoC").delete()

class Migration(migrations.Migration):
    dependencies = [
        ('tournament_creator', '0002_set_admin_role'),
    ]

    operations = [
        migrations.RunPython(create_tournament_type, remove_tournament_type),
    ]