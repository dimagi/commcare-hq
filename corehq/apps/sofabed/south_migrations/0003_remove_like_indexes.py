# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Django adds '_like' indexes to CharFields to improve performance of 'LIKE' queries
        # but since we won't be doing 'LIKE' queries we don't need the indexes

        # Removing 'like' index on 'FormData', fields ['doc_type']
        db.delete_index(u'sofabed_formdata', ['doc_type_like'])

        # Removing 'like' index on 'FormData', fields ['domain']
        db.delete_index(u'sofabed_formdata', ['domain_like'])

        # Removing 'like' index on 'FormData', fields ['xmlns']
        db.delete_index(u'sofabed_formdata', ['xmlns_like'])

        # Removing 'like' index on 'FormData', fields ['app_id']
        db.delete_index(u'sofabed_formdata', ['app_id_like'])

        # Removing 'like' index on 'FormData', fields ['user_id']
        db.delete_index(u'sofabed_formdata', ['user_id_like'])

        # Removing 'like' index on 'FormData', fields ['instance_id']
        db.delete_index(u'sofabed_formdata', ['instance_id_like'])

    def backwards(self, orm):
        pass


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
