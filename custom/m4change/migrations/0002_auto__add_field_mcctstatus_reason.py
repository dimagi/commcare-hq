# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'McctStatus.reason'
        db.add_column(u'm4change_mcctstatus', 'reason', self.gf('django.db.models.fields.CharField')(max_length=32, null=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'McctStatus.reason'
        db.delete_column(u'm4change_mcctstatus', 'reason')


    models = {
        u'm4change.mcctstatus': {
            'Meta': {'object_name': 'McctStatus'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['m4change']
