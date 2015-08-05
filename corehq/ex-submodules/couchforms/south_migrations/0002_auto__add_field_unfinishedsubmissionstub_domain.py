# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'UnfinishedSubmissionStub.domain'
        db.add_column(u'couchforms_unfinishedsubmissionstub', 'domain', self.gf('django.db.models.fields.CharField')(default='', max_length=256), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'UnfinishedSubmissionStub.domain'
        db.delete_column(u'couchforms_unfinishedsubmissionstub', 'domain')


    models = {
        u'couchforms.unfinishedsubmissionstub': {
            'Meta': {'object_name': 'UnfinishedSubmissionStub'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'saved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        }
    }

    complete_apps = ['couchforms']
