# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0004_connectionsettings'),
        ('export', '0008_auto_20190906_2008'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncrementalExport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=255)),
                ('export_instance_id', models.CharField(db_index=True, max_length=126)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('active', models.BooleanField(default=True)),
                ('connection_settings', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='motech.ConnectionSettings')),
            ],
        ),
        migrations.CreateModel(
            name='IncrementalExportCheckpoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('doc_count', models.IntegerField(null=True)),
                ('last_doc_date', models.DateTimeField()),
                ('blob_key', models.UUIDField(default=uuid.uuid4)),
                ('incremental_export', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checkpoints', to='export.IncrementalExport')),
                ('status', models.PositiveSmallIntegerField(choices=[(1, 'success'), (2, 'failure')], null=True)),
                ('request_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='motech.RequestLog', null=True)),
            ],
        ),
    ]
