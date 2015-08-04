# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'FormData'
        db.create_table(u'sofabed_formdata', (
            ('domain', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255, blank=True)),
            ('received_on', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('instance_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255, primary_key=True)),
            ('time_start', self.gf('django.db.models.fields.DateTimeField')()),
            ('time_end', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('duration', self.gf('django.db.models.fields.IntegerField')()),
            ('device_id', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('user_id', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255, blank=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('app_id', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255, blank=True)),
            ('xmlns', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=1000, blank=True)),
        ))
        db.send_create_signal(u'sofabed', ['FormData'])


    def backwards(self, orm):
        
        # Deleting model 'FormData'
        db.delete_table(u'sofabed_formdata')


    models = {
        u'sofabed.formdata': {
            'Meta': {'object_name': 'FormData'},
            'app_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True'}),
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
