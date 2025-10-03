from django.db import migrations

PAIRS_ARCHETYPES = [
    dict(name="2 pairs Swedish format", description="Best of 5 sets, always 1 vs 2, on single field.", tournament_category="PAIRS"),
    dict(name="3 pairs Swedish format", description="Round robin: 3 rounds, 1 field.", tournament_category="PAIRS"),
    dict(name="4 pairs Swedish format", description="Round robin: 3 rounds on 2 fields with 4 pairs.", tournament_category="PAIRS"),
    dict(name="5 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
    dict(name="6 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
    dict(name="7 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
    dict(name="8 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
    dict(name="9 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
    dict(name="10 pairs Swedish format", description="Official pairing from Swedish protokoll.", tournament_category="PAIRS"),
]

def create_swedish_pair_archetypes(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    for row in PAIRS_ARCHETYPES:
        TournamentArchetype.objects.update_or_create(
            name=row["name"],
            defaults=row
        )

class Migration(migrations.Migration):
    dependencies = [
        ("tournament_creator", "0005_eightpairsswedishformat_fourpairsswedishformat_and_more"),
    ]
    operations = [
        migrations.RunPython(create_swedish_pair_archetypes, reverse_code=migrations.RunPython.noop)
    ]
