# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import dimagi.utils.couch.migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0012_add_lastreadmessage_expectedcallback'),
    ]

    operations = [
        migrations.CreateModel(
            name='Call',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('date', models.DateTimeField(null=True, db_index=True)),
                ('couch_recipient_doc_type', models.CharField(max_length=126, null=True, db_index=True)),
                ('couch_recipient', models.CharField(max_length=126, null=True, db_index=True)),
                ('phone_number', models.CharField(max_length=126, null=True, db_index=True)),
                ('direction', models.CharField(max_length=1, null=True)),
                ('error', models.NullBooleanField(default=False)),
                ('system_error_message', models.TextField(null=True)),
                ('system_phone_number', models.CharField(max_length=126, null=True)),
                ('backend_api', models.CharField(max_length=126, null=True)),
                ('backend_id', models.CharField(max_length=126, null=True)),
                ('billed', models.NullBooleanField(default=False)),
                ('workflow', models.CharField(max_length=126, null=True)),
                ('xforms_session_couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('reminder_id', models.CharField(max_length=126, null=True)),
                ('location_id', models.CharField(max_length=126, null=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('answered', models.NullBooleanField(default=False)),
                ('duration', models.IntegerField(null=True)),
                ('gateway_session_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('submit_partial_form', models.NullBooleanField(default=False)),
                ('include_case_side_effects', models.NullBooleanField(default=False)),
                ('max_question_retries', models.IntegerField(null=True)),
                ('current_question_retry_count', models.IntegerField(default=0, null=True)),
                ('xforms_session_id', models.CharField(max_length=126, null=True)),
                ('error_message', models.TextField(null=True)),
                ('use_precached_first_response', models.NullBooleanField(default=False)),
                ('first_response', models.TextField(null=True)),
                ('case_id', models.CharField(max_length=126, null=True)),
                ('case_for_case_submission', models.NullBooleanField(default=False)),
                ('form_unique_id', models.CharField(max_length=126, null=True)),
                ('messaging_subevent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sms.MessagingSubEvent', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
    ]
