# -*- coding: utf-8 -*-

from django.db import models, migrations
import django.db.models.deletion
import dimagi.utils.couch.migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0013_check_for_log_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='QueuedSMS',
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
                ('text', models.TextField(null=True)),
                ('raw_text', models.TextField(null=True)),
                ('datetime_to_process', models.DateTimeField(null=True, db_index=True)),
                ('processed', models.NullBooleanField(default=True, db_index=True)),
                ('num_processing_attempts', models.IntegerField(default=0, null=True)),
                ('queued_timestamp', models.DateTimeField(null=True)),
                ('processed_timestamp', models.DateTimeField(null=True)),
                ('domain_scope', models.CharField(max_length=126, null=True)),
                ('ignore_opt_out', models.NullBooleanField(default=False)),
                ('backend_message_id', models.CharField(max_length=126, null=True)),
                ('chat_user_id', models.CharField(max_length=126, null=True)),
                ('invalid_survey_response', models.NullBooleanField(default=False)),
                ('fri_message_bank_lookup_completed', models.NullBooleanField(default=False)),
                ('fri_message_bank_message_id', models.CharField(max_length=126, null=True)),
                ('fri_id', models.CharField(max_length=126, null=True)),
                ('fri_risk_profile', models.CharField(max_length=1, null=True)),
                ('messaging_subevent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sms.MessagingSubEvent', null=True)),
            ],
            options={
                'db_table': 'sms_queued',
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
    ]
