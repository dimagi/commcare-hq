# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import dimagi.utils.couch.migration
import uuidfield.fields
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0002_add_selfregistrationinvitation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLMobileBackend',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('backend_type', models.CharField(default=b'SMS', max_length=3, choices=[(b'SMS', 'SMS'), (b'IVR', 'IVR')])),
                ('inbound_api_key', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('hq_api_id', models.CharField(max_length=126, null=True)),
                ('is_global', models.BooleanField(default=False)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('name', models.CharField(max_length=126)),
                ('display_name', models.CharField(max_length=126, null=True)),
                ('description', models.TextField(null=True)),
                ('supported_countries', json_field.fields.JSONField(default=[], help_text='Enter a valid JSON object')),
                ('extra_fields', json_field.fields.JSONField(default={}, help_text='Enter a valid JSON object')),
                ('deleted', models.BooleanField(default=False)),
                ('load_balancing_numbers', json_field.fields.JSONField(default=[], help_text='Enter a valid JSON object')),
                ('reply_to_phone_number', models.CharField(max_length=126, null=True)),
            ],
            options={
                'db_table': 'messaging_mobilebackend',
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SQLMobileBackendMapping',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('is_global', models.BooleanField(default=False)),
                ('domain', models.CharField(max_length=126, null=True)),
                ('backend_type', models.CharField(max_length=3, choices=[(b'SMS', 'SMS'), (b'IVR', 'IVR')])),
                ('prefix', models.CharField(max_length=25)),
                ('backend', models.ForeignKey(to='sms.SQLMobileBackend')),
            ],
            options={
                'db_table': 'messaging_mobilebackendmapping',
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
        migrations.CreateModel(
            name='MobileBackendInvitation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('backend', models.ForeignKey(to='sms.SQLMobileBackend')),
                ('accepted', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'messaging_mobilebackendinvitation',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='sqlmobilebackend',
            unique_together=set([('domain', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='mobilebackendinvitation',
            unique_together=set([('backend', 'domain')]),
        ),
        migrations.CreateModel(
            name='SQLSMSBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlmobilebackend',),
        ),
        migrations.CreateModel(
            name='SQLMegamobileBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLMachBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLHttpBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLSislogBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlhttpbackend',),
        ),
        migrations.CreateModel(
            name='SQLGrapevineBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLAppositBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLSMSGHBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLTelerivetBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLTestSMSBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLTropoBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLTwilioBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLUnicelBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='SQLYoBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlhttpbackend',),
        ),
        migrations.AlterField(
            model_name='messagingevent',
            name='recipient_type',
            field=models.CharField(db_index=True, max_length=3, null=True, choices=[(b'CAS', b'Case'), (b'MOB', b'Mobile Worker'), (b'WEB', b'Web User'), (b'UGP', b'User Group'), (b'CGP', b'Case Group'), (b'MUL', b'Multiple Recipients'), (b'LOC', b'Location'), (b'LC+', b'Location (including child locations)'), (b'VLC', b'Multiple Locations'), (b'VL+', b'Multiple Locations (including child locations)'), (b'UNK', b'Unknown Contact')]),
            preserve_default=True,
        ),
    ]
