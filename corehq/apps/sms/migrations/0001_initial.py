import django.db.models.deletion
from django.db import migrations, models

import dimagi.utils.couch.migration

import corehq.apps.sms.models


class Migration(migrations.Migration):

    dependencies = [
        ('smsforms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessagingEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, db_index=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('source', models.CharField(max_length=3, choices=[('BRD', 'Broadcast'), ('KWD', 'Keyword'), ('RMD', 'Reminder'), ('UNR', 'Unrecognized'), ('FWD', 'Forwarded Message'), ('OTH', 'Other')])),
                ('source_id', models.CharField(max_length=126, null=True)),
                ('content_type', models.CharField(max_length=3, choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email')])),
                ('form_unique_id', models.CharField(max_length=126, null=True)),
                ('form_name', models.TextField(null=True)),
                ('status', models.CharField(max_length=3, choices=[('PRG', 'In Progress'), ('CMP', 'Completed'), ('NOT', 'Not Completed'), ('ERR', 'Error')])),
                ('error_code', models.CharField(max_length=126, null=True)),
                ('additional_error_text', models.TextField(null=True)),
                ('recipient_type', models.CharField(db_index=True, max_length=3, null=True, choices=[('CAS', 'Case'), ('MOB', 'Mobile Worker'), ('WEB', 'Web User'), ('UGP', 'User Group'), ('CGP', 'Case Group'), ('MUL', 'Multiple Recipients'), ('UNK', 'Unknown Contact')])),
                ('recipient_id', models.CharField(max_length=126, null=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model, corehq.apps.sms.models.MessagingStatusMixin),
        ),
        migrations.CreateModel(
            name='MessagingSubEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('recipient_type', models.CharField(max_length=3, choices=[('CAS', 'Case'), ('MOB', 'Mobile Worker'), ('WEB', 'Web User')])),
                ('recipient_id', models.CharField(max_length=126, null=True)),
                ('content_type', models.CharField(max_length=3, choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email')])),
                ('form_unique_id', models.CharField(max_length=126, null=True)),
                ('form_name', models.TextField(null=True)),
                ('case_id', models.CharField(max_length=126, null=True)),
                ('status', models.CharField(max_length=3, choices=[('PRG', 'In Progress'), ('CMP', 'Completed'), ('NOT', 'Not Completed'), ('ERR', 'Error')])),
                ('error_code', models.CharField(max_length=126, null=True)),
                ('additional_error_text', models.TextField(null=True)),
                ('parent', models.ForeignKey(to='sms.MessagingEvent', on_delete=models.CASCADE)),
                ('xforms_session', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='smsforms.SQLXFormsSession', null=True)),
            ],
            options={
            },
            bases=(models.Model, corehq.apps.sms.models.MessagingStatusMixin),
        ),
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('phone_number', models.CharField(unique=True, max_length=30, db_index=True)),
                ('send_sms', models.BooleanField(default=True)),
                ('send_ivr', models.BooleanField(default=True)),
                ('can_opt_in', models.BooleanField(default=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SMS',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('date', models.DateTimeField(null=True, db_index=True)),
                ('couch_recipient_doc_type', models.CharField(max_length=126, null=True, db_index=True)),
                ('couch_recipient', models.CharField(max_length=126, null=True, db_index=True)),
                ('phone_number', models.CharField(max_length=126, null=True, db_index=True)),
                ('direction', models.CharField(max_length=1, null=True)),
                ('text', models.TextField(null=True)),
                ('raw_text', models.TextField(null=True)),
                ('datetime_to_process', models.DateTimeField(null=True, db_index=True)),
                ('processed', models.NullBooleanField(default=True, db_index=True)),
                ('num_processing_attempts', models.IntegerField(default=0, null=True)),
                ('queued_timestamp', models.DateTimeField(null=True)),
                ('processed_timestamp', models.DateTimeField(null=True)),
                ('error', models.NullBooleanField(default=False)),
                ('system_error_message', models.TextField(null=True)),
                ('billed', models.NullBooleanField(default=False)),
                ('domain_scope', models.CharField(max_length=126, null=True)),
                ('ignore_opt_out', models.NullBooleanField(default=False)),
                ('backend_api', models.CharField(max_length=126, null=True)),
                ('backend_id', models.CharField(max_length=126, null=True)),
                ('system_phone_number', models.CharField(max_length=126, null=True)),
                ('backend_message_id', models.CharField(max_length=126, null=True)),
                ('workflow', models.CharField(max_length=126, null=True)),
                ('chat_user_id', models.CharField(max_length=126, null=True)),
                ('xforms_session_couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('invalid_survey_response', models.NullBooleanField(default=False)),
                ('reminder_id', models.CharField(max_length=126, null=True)),
                ('location_id', models.CharField(max_length=126, null=True)),
                ('fri_message_bank_lookup_completed', models.NullBooleanField(default=False)),
                ('fri_message_bank_message_id', models.CharField(max_length=126, null=True)),
                ('fri_id', models.CharField(max_length=126, null=True)),
                ('fri_risk_profile', models.CharField(max_length=1, null=True)),
                ('messaging_subevent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sms.MessagingSubEvent', null=True)),
            ],
            options={
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
    ]
