# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'PillowError'
        db.create_table(u'pillow_retry_pillowerror', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('doc_id', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('pillow', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')()),
            ('date_last_attempt', self.gf('django.db.models.fields.DateTimeField')()),
            ('date_next_attempt', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('total_attempts', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('current_attempt', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('error_message', self.gf('django.db.models.fields.CharField')(max_length=512, null=True)),
            ('error_type', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('error_traceback', self.gf('django.db.models.fields.TextField')(null=True)),
        ))
        db.send_create_signal(u'pillow_retry', ['PillowError'])


    def backwards(self, orm):
        
        # Deleting model 'PillowError'
        db.delete_table(u'pillow_retry_pillowerror')


    models = {
        u'pillow_retry.pillowerror': {
            'Meta': {'object_name': 'PillowError'},
            'current_attempt': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {}),
            'date_last_attempt': ('django.db.models.fields.DateTimeField', [], {}),
            'date_next_attempt': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'doc_id': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'error_message': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'error_traceback': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'error_type': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'pillow': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'total_attempts': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['pillow_retry']
