# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocationType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('code', models.SlugField(null=True, db_index=False)),
                ('administrative', models.BooleanField(default=False)),
                ('shares_cases', models.BooleanField(default=False)),
                ('view_descendants', models.BooleanField(default=False)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('emergency_level', models.DecimalField(default=0.5, max_digits=10, decimal_places=1)),
                ('understock_threshold', models.DecimalField(default=1.5, max_digits=10, decimal_places=1)),
                ('overstock_threshold', models.DecimalField(default=3.0, max_digits=10, decimal_places=1)),
                ('parent_type', models.ForeignKey(to='locations.LocationType', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SQLLocation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('location_id', models.CharField(unique=True, max_length=100, db_index=True)),
                ('site_code', models.CharField(max_length=255)),
                ('external_id', models.CharField(max_length=255, null=True)),
                ('metadata', json_field.fields.JSONField(default={}, help_text='Enter a valid JSON object')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('latitude', models.DecimalField(null=True, max_digits=20, decimal_places=10)),
                ('longitude', models.DecimalField(null=True, max_digits=20, decimal_places=10)),
                ('stocks_all_products', models.BooleanField(default=True)),
                ('supply_point_id', models.CharField(max_length=255, unique=True, null=True, db_index=True)),
                ('lft', models.PositiveIntegerField(editable=False, db_index=True)),
                ('rght', models.PositiveIntegerField(editable=False, db_index=True)),
                ('tree_id', models.PositiveIntegerField(editable=False, db_index=True)),
                ('level', models.PositiveIntegerField(editable=False, db_index=True)),
                ('_products', models.ManyToManyField(to='products.SQLProduct', null=True)),
                ('location_type', models.ForeignKey(to='locations.LocationType')),
                ('parent', mptt.fields.TreeForeignKey(related_name='children', blank=True, to='locations.SQLLocation', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='sqllocation',
            unique_together=set([('domain', 'site_code')]),
        ),
    ]
