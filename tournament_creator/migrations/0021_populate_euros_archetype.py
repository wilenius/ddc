# Data migration: create the euros format archetype row.

from django.db import migrations


def create_euros_archetype(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    TournamentArchetype.objects.get_or_create(
        name='20 pairs euros format',
        defaults={
            'description': 'Euros format: 5 pools of 4, then A/B pools of 10, then placement groups of 4.',
            'tournament_category': 'PAIRS',
            'notes': (
                'Used at European Open 2024/2026. Phase 1: 5 pools of 4 (snake seeding), '
                'round robin. Top 2 of each pool advance to the A Pool, bottom 2 to the B Pool. '
                'Phase 2: full round robin within each pool of 10. The resulting provisional '
                'order (A Pool 1-10, B Pool 11-20) is split into groups of 4 that play semis '
                '(1v4, 2v3) and placement matches. Every pair plays 14 matches.'
            ),
        },
    )


def remove_euros_archetype(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    TournamentArchetype.objects.filter(name='20 pairs euros format').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0020_eurosformat_pool_matchup_pool_poolpair_pool_pairs_and_more'),
    ]

    operations = [
        migrations.RunPython(create_euros_archetype, reverse_code=remove_euros_archetype),
    ]
