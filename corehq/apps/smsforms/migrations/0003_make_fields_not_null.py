# Generated by Django 1.11.8 on 2018-01-19 18:12

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smsforms', '0002_add_state_tracking_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqlxformssession',
            name='current_action_due',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='sqlxformssession',
            name='current_reminder_num',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='sqlxformssession',
            name='expire_after',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='sqlxformssession',
            name='phone_number',
            field=models.CharField(max_length=126),
        ),
        migrations.AlterField(
            model_name='sqlxformssession',
            name='reminder_intervals',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list),
        ),
        migrations.AlterField(
            model_name='sqlxformssession',
            name='session_is_open',
            field=models.BooleanField(default=True),
        ),
    ]
