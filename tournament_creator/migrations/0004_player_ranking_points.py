# Generated by Django 5.1.5 on 2025-04-11 16:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0003_tournament_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='ranking_points',
            field=models.FloatField(default=0),
        ),
    ]
