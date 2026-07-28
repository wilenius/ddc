from django.db import migrations


def set_default_location(apps, schema_editor):
    """Every tournament that existed before location metadata was added was
    played in Helsinki, Finland."""
    TournamentChart = apps.get_model('tournament_creator', 'TournamentChart')
    TournamentChart.objects.filter(place='').update(place='Helsinki')
    TournamentChart.objects.filter(country='').update(country='Finland')


def unset_location(apps, schema_editor):
    TournamentChart = apps.get_model('tournament_creator', 'TournamentChart')
    TournamentChart.objects.filter(place='Helsinki', country='Finland').update(place='', country='')


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0029_tournamentchart_country_tournamentchart_created_by_and_more'),
    ]

    operations = [
        migrations.RunPython(set_default_location, unset_location),
    ]
