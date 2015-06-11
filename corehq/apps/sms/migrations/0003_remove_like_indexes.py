# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        db.execute("DROP INDEX IF EXISTS sms_sms_couch_id_like")
        db.execute("DROP INDEX IF EXISTS sms_sms_couch_recipient_doc_type_like")
        db.execute("DROP INDEX IF EXISTS sms_sms_couch_recipient_like")
        db.execute("DROP INDEX IF EXISTS sms_sms_domain_like")
        db.execute("DROP INDEX IF EXISTS sms_sms_phone_number_like")
        db.execute("DROP INDEX IF EXISTS sms_sms_xforms_session_couch_id_like")

    def backwards(self, orm):
        # don't add it back
        pass

    models = {
        'sms.phonenumber': {
            'Meta': {'object_name': 'PhoneNumber'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True', 'null': 'False', 'db_index': 'True'}),
            'send_sms': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'send_ivr': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'can_opt_in': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
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
        },
    }

    complete_apps = ['sms']
