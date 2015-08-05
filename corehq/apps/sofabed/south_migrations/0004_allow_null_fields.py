# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Changing field 'FormData.username'
        db.alter_column(u'sofabed_formdata', 'username', self.gf('django.db.models.fields.CharField')(max_length=255, null=True))

        # Changing field 'FormData.xmlns'
        db.alter_column(u'sofabed_formdata', 'xmlns', self.gf('django.db.models.fields.CharField')(max_length=1000, null=True))

        # Changing field 'FormData.app_id'
        db.alter_column(u'sofabed_formdata', 'app_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True))

        # Changing field 'FormData.user_id'
        db.alter_column(u'sofabed_formdata', 'user_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True))

        # Changing field 'FormData.device_id'
        db.alter_column(u'sofabed_formdata', 'device_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True))


    def backwards(self, orm):
        
        # Changing field 'FormData.username'
        db.alter_column(u'sofabed_formdata', 'username', self.gf('django.db.models.fields.CharField')(default='', max_length=255))

        # Changing field 'FormData.xmlns'
        db.alter_column(u'sofabed_formdata', 'xmlns', self.gf('django.db.models.fields.CharField')(default='', max_length=1000))

        # Changing field 'FormData.app_id'
        db.alter_column(u'sofabed_formdata', 'app_id', self.gf('django.db.models.fields.CharField')(default='', max_length=255))

        # Changing field 'FormData.user_id'
        db.alter_column(u'sofabed_formdata', 'user_id', self.gf('django.db.models.fields.CharField')(default='', max_length=255))

        # Changing field 'FormData.device_id'
        db.alter_column(u'sofabed_formdata', 'device_id', self.gf('django.db.models.fields.CharField')(default='', max_length=255))


    models = {
        u'sofabed.formdata': {
            'Meta': {'object_name': 'FormData'},
            'app_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'doc_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'duration': ('django.db.models.fields.IntegerField', [], {}),
            'instance_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'primary_key': 'True'}),
            'received_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_end': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_start': ('django.db.models.fields.DateTimeField', [], {}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'xmlns': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'db_index': 'True'})
        }
    }

    complete_apps = ['sofabed']
