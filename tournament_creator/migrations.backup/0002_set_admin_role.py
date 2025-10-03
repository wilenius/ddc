from django.db import migrations

def set_admin_role(apps, schema_editor):
    User = apps.get_model('tournament_creator', 'User')
    admin = User.objects.filter(username='admin').first()
    if admin:
        admin.role = 'ADMIN'
        admin.save()

def reverse_admin_role(apps, schema_editor):
    User = apps.get_model('tournament_creator', 'User')
    admin = User.objects.filter(username='admin').first()
    if admin:
        admin.role = 'SPECTATOR'
        admin.save()

class Migration(migrations.Migration):
    dependencies = [
        ('tournament_creator', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_admin_role, reverse_admin_role),
    ]