# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'UnfinishedSubmissionStub'
        db.create_table(u'couchforms_unfinishedsubmissionstub', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')()),
            ('saved', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'couchforms', ['UnfinishedSubmissionStub'])


    def backwards(self, orm):
        
        # Deleting model 'UnfinishedSubmissionStub'
        db.delete_table(u'couchforms_unfinishedsubmissionstub')


    models = {
        u'couchforms.unfinishedsubmissionstub': {
            'Meta': {'object_name': 'UnfinishedSubmissionStub'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'saved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        }
    }

    complete_apps = ['couchforms']
