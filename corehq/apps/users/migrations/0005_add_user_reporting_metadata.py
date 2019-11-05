# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-10-24 23:15
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_rm_role_id_from_admins'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserReportingMetadataStaging',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.TextField()),
                ('user_id', models.TextField()),
                ('app_id', models.TextField()),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('build_id', models.TextField(null=True)),
                ('xform_version', models.IntegerField(null=True)),
                ('form_meta', django.contrib.postgres.fields.jsonb.JSONField(null=True)),
                ('received_on', models.DateTimeField(null=True)),
                ('device_id', models.TextField(null=True)),
                ('sync_date', models.DateTimeField(null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='userreportingmetadatastaging',
            unique_together=set([('domain', 'user_id', 'app_id')]),
        ),
    ]
