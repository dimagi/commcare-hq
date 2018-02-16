# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MigrationCheckpoint',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100)),
                ('date', models.DateTimeField(null=True, blank=True)),
                ('start_date', models.DateTimeField(null=True, blank=True)),
                ('api', models.CharField(max_length=100)),
                ('limit', models.PositiveIntegerField()),
                ('offset', models.PositiveIntegerField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StockDataCheckpoint',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100)),
                ('date', models.DateTimeField(null=True, blank=True)),
                ('start_date', models.DateTimeField(null=True, blank=True)),
                ('api', models.CharField(max_length=100)),
                ('limit', models.PositiveIntegerField()),
                ('offset', models.PositiveIntegerField()),
                ('location', models.ForeignKey(blank=True, to='locations.SQLLocation', null=True, on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
