# Generated by Django 4.2.17 on 2025-01-17 13:43

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ExperimentEnabler',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campaign', models.CharField(help_text='Identifier for a group of related experiments.', max_length=255)),
                ('path', models.CharField(blank=True, help_text='Example: corehq.apps.experiments.func Partial paths may be specified to match all experiments in a namespace. An empty string matches all experiments.', max_length=1024)),
                ('enabled_percent', models.SmallIntegerField(default=0, help_text='0 means run only old, -1 to disable metrics as well. 1-100 means % of time to run new. 101 means run only new, 102 to disable metrics as well.', validators=[django.core.validators.MinValueValidator(-1), django.core.validators.MaxValueValidator(102)])),
            ],
            options={
                'unique_together': {('campaign', 'path')},
            },
        ),
    ]
