from django.db import migrations

MOC_ARCHETYPES = [
    dict(name="5-player Monarch of the Court", description="MoC: 5-player specific schedule (Option A).", tournament_category="MOC"),
    dict(name="6-player Monarch of the Court", description="MoC: 6-player specific schedule (Option A).", tournament_category="MOC"),
    dict(name="7-player Monarch of the Court", description="MoC: 7-player specific schedule.", tournament_category="MOC"),
    dict(name="9-player Monarch of the Court", description="MoC: 9-player specific schedule with 2 courts.", tournament_category="MOC"),
    dict(name="10-player Monarch of the Court", description="MoC: 10-player specific schedule with 2 courts.", tournament_category="MOC"),
    dict(name="11-player Monarch of the Court", description="MoC: 11-player specific schedule with 2 courts.", tournament_category="MOC"),
    dict(name="12-player Monarch of the Court", description="MoC: 12-player specific schedule with 3 courts.", tournament_category="MOC"),
    dict(name="13-player Monarch of the Court", description="MoC: 13-player specific schedule with 3 courts.", tournament_category="MOC"),
    dict(name="14-player Monarch of the Court", description="MoC: 14-player specific schedule with 3 courts.", tournament_category="MOC"),
    dict(name="15-player Monarch of the Court", description="MoC: 15-player specific schedule with 3 courts.", tournament_category="MOC"),
    dict(name="16-player Monarch of the Court", description="MoC: 16-player specific schedule with 4 courts.", tournament_category="MOC"),
]

def create_moc_archetypes(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    for row in MOC_ARCHETYPES:
        TournamentArchetype.objects.update_or_create(
            name=row["name"],
            defaults=row
        )

class Migration(migrations.Migration):
    dependencies = [
        ("tournament_creator", "0006_create_swedish_pair_archetypes"),
    ]
    operations = [
        migrations.RunPython(create_moc_archetypes, reverse_code=migrations.RunPython.noop)
    ]