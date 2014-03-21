# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'FormData.doc_type'
        db.add_column(u'sofabed_formdata', 'doc_type', self.gf('django.db.models.fields.CharField')(default='XFormInstance', max_length=255, db_index=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'FormData.doc_type'
        db.delete_column(u'sofabed_formdata', 'doc_type')


    models = {
        u'sofabed.formdata': {
            'Meta': {'object_name': 'FormData'},
            'app_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'doc_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'duration': ('django.db.models.fields.IntegerField', [], {}),
            'instance_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'primary_key': 'True'}),
            'received_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_end': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_start': ('django.db.models.fields.DateTimeField', [], {}),
            'user_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'xmlns': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '1000', 'blank': 'True'})
        }
    }

    complete_apps = ['sofabed']
