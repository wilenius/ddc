import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('tournament_creator', '0007_create_moc_archetypes'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonarchOfTheCourt5',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt6',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt7',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt9',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt10',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt11',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt12',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt13',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt14',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt15',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
        migrations.CreateModel(
            name='MonarchOfTheCourt16',
            fields=[
                ('tournamentarchetype_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tournament_creator.tournamentarchetype')),
            ],
            bases=('tournament_creator.tournamentarchetype',),
        ),
    ]