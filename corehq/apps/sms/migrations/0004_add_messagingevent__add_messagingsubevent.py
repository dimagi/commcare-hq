# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ('smsforms', '0003_auto__chg_field_sqlxformssession_couch_id'),
    )

    def forwards(self, orm):

        # Adding model 'MessagingEvent'
        db.create_table('sms_messagingevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=126, null=False, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=False, db_index=True)),
            ('source', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('source_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('content_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('form_unique_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('form_name', self.gf('django.db.models.fields.TextField')(null=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('error_code', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('additional_error_text', self.gf('django.db.models.fields.TextField')(null=True)),
            ('recipient_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=True, db_index=True)),
            ('recipient_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True, db_index=True)),
        ))
        db.send_create_signal('sms', ['MessagingEvent'])

        # Adding model 'MessagingSubEvent'
        db.create_table('sms_messagingsubevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['sms.MessagingEvent'])),
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=False, db_index=True)),
            ('recipient_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('recipient_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('content_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('form_unique_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('form_name', self.gf('django.db.models.fields.TextField')(null=True)),
            ('xforms_session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['smsforms.SQLXFormsSession'], null=True)),
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('error_code', self.gf('django.db.models.fields.CharField')(max_length=126, null=True)),
            ('additional_error_text', self.gf('django.db.models.fields.TextField')(null=True)),
        ))
        db.send_create_signal('sms', ['MessagingSubEvent'])

        # Add foreign key to MessagingSubEvent on SMS
        db.add_column('sms_sms', 'messaging_subevent', self.gf('django.db.models.ForeignKey')(to=orm['sms.MessagingSubEvent'], null=True))

    def backwards(self, orm):
        
        # Deleting model 'MessagingEvent'
        db.delete_table('sms_messagingevent')

        # Deleting model 'MessagingSubEvent'
        db.delete_table('sms_messagingsubevent')

        # Remove foreign key to MessagingSubEvent from SMS
        db.delete_column('sms_sms', 'messaging_subevent_id')

    models = {
        u'smsforms.sqlxformssession': {
            'Meta': {'object_name': 'SQLXFormsSession'},
            'app_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'connection_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'couch_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'form_xmlns': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified_time': ('django.db.models.fields.DateTimeField', [], {}),
            'reminder_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'session_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'session_type': ('django.db.models.fields.CharField', [], {'default': "'SMS'", 'max_length': '10'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {}),
            'submission_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'survey_incentive': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
        },
        'sms.phonenumber': {
            'Meta': {'object_name': 'PhoneNumber'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True', 'null': 'False', 'db_index': 'True'}),
            'send_sms': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'send_ivr': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'can_opt_in': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
        },
        'sms.messagingevent': {
            'Meta': {'object_name': 'MessagingEvent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'False', 'db_index': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'False', 'db_index': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'source_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'content_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'form_unique_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'form_name': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'error_code': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'additional_error_text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'recipient_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'db_index': 'True'}),
            'recipient_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
        },
        'sms.messagingsubevent': {
            'Meta': {'object_name': 'MessagingSubEvent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sms.MessagingEvent']"}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'False', 'db_index': 'True'}),
            'recipient_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'recipient_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'content_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'form_unique_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'form_name': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'xforms_session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['smsforms.SQLXFormsSession']", 'null': 'True'}),
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'error_code': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'additional_error_text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
        },
        'sms.sms': {
            'Meta': {'object_name': 'SMS'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'couch_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'couch_recipient_doc_type': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'couch_recipient': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'direction': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'raw_text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'datetime_to_process': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'processed': ('django.db.models.fields.NullBooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'num_processing_attempts': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'queued_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'processed_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'error': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            'system_error_message': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'billed': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            'domain_scope': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'ignore_opt_out': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            'backend_api': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'backend_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'system_phone_number': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'backend_message_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'workflow': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'chat_user_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'xforms_session_couch_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True', 'db_index': 'True'}),
            'invalid_survey_response': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            'reminder_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'location_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'fri_message_bank_lookup_completed': ('django.db.models.fields.NullBooleanField', [], {'default': 'False'}),
            'fri_message_bank_message_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'fri_id': ('django.db.models.fields.CharField', [], {'max_length': '126', 'null': 'True'}),
            'fri_risk_profile': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True'}),
            'messaging_subevent': ('django.db.models.ForeignKey', [], {'to': "orm['sms.MessagingSubEvent']", 'null': 'True'}),
        },
    }

    complete_apps = ['sms']
