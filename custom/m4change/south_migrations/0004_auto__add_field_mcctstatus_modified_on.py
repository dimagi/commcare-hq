# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'McctStatus.modified_on'
        db.add_column(u'm4change_mcctstatus', 'modified_on', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, default=datetime.date(2014, 5, 27), blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'McctStatus.modified_on'
        db.delete_column(u'm4change_mcctstatus', 'modified_on')


    models = {
        u'm4change.mcctstatus': {
            'Meta': {'object_name': 'McctStatus'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'immunized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_booking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified_on': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'received_on': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'registration_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['m4change']
