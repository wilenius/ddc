# Generated by Django 5.1.5 on 2025-05-26 12:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament_creator', '0010_update_tournament_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationBackendSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('backend_name', models.CharField(choices=[('email', 'Email'), ('signal', 'Signal'), ('matrix', 'Matrix')], max_length=50, unique=True)),
                ('is_active', models.BooleanField(default=False)),
                ('config', models.JSONField(blank=True, null=True)),
            ],
        ),
        migrations.AlterModelOptions(
            name='tournamentarchetype',
            options={'ordering': ['tournament_category', 'name']},
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField()),
                ('details', models.TextField(blank=True)),
                ('backend_setting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tournament_creator.notificationbackendsetting')),
                ('match_result_log', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tournament_creator.matchresultlog')),
            ],
        ),
    ]
