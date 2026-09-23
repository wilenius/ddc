# Data migration: create the archetype rows of the multi-phase pairs formats.

from django.db import migrations

ARCHETYPES = [
    {
        'name': 'Round robin + top-4 playoffs',
        'description': 'Round robin, then semifinals, final and bronze match for the top 4.',
        'notes': (
            'Stage 1: everyone plays everyone once. Stage 2: the top 4 play semifinals '
            '(1v4, 2v3); the winners play the final and the losers the bronze match. '
            'The other pairs are placed by the round robin. 4-10 pairs.'
        ),
    },
    {
        'name': 'Double round robin, reseeded',
        'description': 'Two round robins; the second is reseeded by the first.',
        'notes': (
            'Everyone plays everyone twice (Uppsala style). The second round robin is '
            'reseeded by the first round robin standings, so the top two meet in the last '
            'round and the leader plays every match on court 1. Standings count both '
            'round robins. 3-10 pairs.'
        ),
    },
]


def create_archetypes(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    for archetype in ARCHETYPES:
        TournamentArchetype.objects.get_or_create(
            name=archetype['name'],
            defaults={
                'description': archetype['description'],
                'tournament_category': 'PAIRS',
                'notes': archetype['notes'],
            },
        )


def remove_archetypes(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    TournamentArchetype.objects.filter(name__in=[a['name'] for a in ARCHETYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0031_multi_phase_pairs_formats'),
    ]

    operations = [
        migrations.RunPython(create_archetypes, reverse_code=remove_archetypes),
    ]
