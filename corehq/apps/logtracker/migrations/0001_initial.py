# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'LogTrack'
        db.create_table('logtracker_logtrack', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('level', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('channel', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('message', self.gf('django.db.models.fields.TextField')(null=True)),
            ('pathname', self.gf('django.db.models.fields.TextField')(null=True)),
            ('funcname', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('module', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('filename', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('line_no', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('traceback', self.gf('django.db.models.fields.TextField')(null=True)),
            ('data_dump', self.gf('django.db.models.fields.TextField')(null=True)),
        ))
        db.send_create_signal('logtracker', ['LogTrack'])


    def backwards(self, orm):
        
        # Deleting model 'LogTrack'
        db.delete_table('logtracker_logtrack')


    models = {
        'logtracker.logtrack': {
            'Meta': {'object_name': 'LogTrack'},
            'channel': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'data_dump': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'funcname': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'line_no': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'pathname': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'traceback': ('django.db.models.fields.TextField', [], {'null': 'True'})
        }
    }

    complete_apps = ['logtracker']
