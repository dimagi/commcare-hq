# encoding: utf-8
from __future__ import absolute_import
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'PillowError.change'
        db.add_column(u'pillow_retry_pillowerror', 'change', self.gf('django.db.models.fields.TextField')(null=True), keep_default=False)

    def backwards(self, orm):
        
        # Deleting field 'PillowError.change'
        db.delete_column(u'pillow_retry_pillowerror', 'change')

    models = {
        u'pillow_retry.pillowerror': {
            'Meta': {'unique_together': "(('doc_id', 'pillow'),)", 'object_name': 'PillowError'},
            'change': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'current_attempt': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {}),
            'date_last_attempt': ('django.db.models.fields.DateTimeField', [], {}),
            'date_next_attempt': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'doc_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'error_traceback': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'error_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pillow': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'total_attempts': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['pillow_retry']
