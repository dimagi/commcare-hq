# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding index on 'PillowError', fields ['current_attempt']
        db.create_index(u'pillow_retry_pillowerror', ['current_attempt'])

        # Adding index on 'PillowError', fields ['date_next_attempt']
        db.create_index(u'pillow_retry_pillowerror', ['date_next_attempt'])

        # Adding index on 'PillowError', fields ['doc_id']
        db.create_index(u'pillow_retry_pillowerror', ['doc_id'])


    def backwards(self, orm):
        
        # Removing index on 'PillowError', fields ['doc_id']
        db.delete_index(u'pillow_retry_pillowerror', ['doc_id'])

        # Removing index on 'PillowError', fields ['date_next_attempt']
        db.delete_index(u'pillow_retry_pillowerror', ['date_next_attempt'])

        # Removing index on 'PillowError', fields ['current_attempt']
        db.delete_index(u'pillow_retry_pillowerror', ['current_attempt'])


    models = {
        u'pillow_retry.pillowerror': {
            'Meta': {'object_name': 'PillowError'},
            'current_attempt': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {}),
            'date_last_attempt': ('django.db.models.fields.DateTimeField', [], {}),
            'date_next_attempt': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True'}),
            'doc_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'error_message': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True'}),
            'error_traceback': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'error_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pillow': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'total_attempts': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['pillow_retry']
