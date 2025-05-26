from django.db import migrations

def update_tournament_names(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    
    # Update Swedish format names to doubles tournament names
    name_mappings = {
        "4 pairs Swedish format": "4 pairs doubles tournament",
        "8 pairs Swedish format": "8 pairs doubles tournament",
        "Cade Loving's 8-player KoC": "8-player Monarch of the Court"
    }
    
    for old_name, new_name in name_mappings.items():
        try:
            archetype = TournamentArchetype.objects.get(name=old_name)
            archetype.name = new_name
            archetype.save()
        except TournamentArchetype.DoesNotExist:
            # If the old name doesn't exist, create the new one if needed
            TournamentArchetype.objects.get_or_create(
                name=new_name,
                defaults={
                    'tournament_category': 'MOC' if 'Monarch' in new_name else 'PAIRS',
                    'description': f"Updated tournament format: {new_name}"
                }
            )

def reverse_tournament_names(apps, schema_editor):
    TournamentArchetype = apps.get_model('tournament_creator', 'TournamentArchetype')
    
    # Reverse the name mappings
    name_mappings = {
        "4 pairs doubles tournament": "4 pairs Swedish format",
        "8 pairs doubles tournament": "8 pairs Swedish format", 
        "8-player Monarch of the Court": "Cade Loving's 8-player KoC"
    }
    
    for new_name, old_name in name_mappings.items():
        try:
            archetype = TournamentArchetype.objects.get(name=new_name)
            archetype.name = old_name
            archetype.save()
        except TournamentArchetype.DoesNotExist:
            pass

class Migration(migrations.Migration):
    dependencies = [
        ("tournament_creator", "0009_rankingsupdate"),
    ]
    operations = [
        migrations.RunPython(update_tournament_names, reverse_code=reverse_tournament_names)
    ]