# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        db.execute("DROP INDEX IF EXISTS m4change_mcctstatus_domain_like")
        db.execute("DROP INDEX IF EXISTS m4change_mcctstatus_form_id_like")

    def backwards(self, orm):
        # don't add it back
        pass


    models = {
        u'm4change.mcctstatus': {
            'Meta': {'object_name': 'McctStatus'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'immunized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_booking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_stillbirth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified_on': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'received_on': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'registration_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'user': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'})
        }
    }

    complete_apps = ['m4change']
