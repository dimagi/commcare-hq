# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'McctStatus'
        db.create_table(u'm4change_mcctstatus', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('form_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=256, null=True, db_index=True)),
        ))
        db.send_create_signal(u'm4change', ['McctStatus'])


    def backwards(self, orm):
        
        # Deleting model 'McctStatus'
        db.delete_table(u'm4change_mcctstatus')


    models = {
        u'm4change.mcctstatus': {
            'Meta': {'object_name': 'McctStatus'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['m4change']
