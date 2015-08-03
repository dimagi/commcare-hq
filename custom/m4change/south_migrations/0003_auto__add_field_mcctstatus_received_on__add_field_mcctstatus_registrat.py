# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding field 'McctStatus.received_on'
        db.add_column(u'm4change_mcctstatus', 'received_on', self.gf('django.db.models.fields.DateField')(null=True), keep_default=False)

        # Adding field 'McctStatus.registration_date'
        db.add_column(u'm4change_mcctstatus', 'registration_date', self.gf('django.db.models.fields.DateField')(null=True), keep_default=False)

        # Adding field 'McctStatus.immunized'
        db.add_column(u'm4change_mcctstatus', 'immunized', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # Adding field 'McctStatus.is_booking'
        db.add_column(u'm4change_mcctstatus', 'is_booking', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # Adding unique constraint on 'McctStatus', fields ['form_id']
        db.create_unique(u'm4change_mcctstatus', ['form_id'])


    def backwards(self, orm):

        # Removing unique constraint on 'McctStatus', fields ['form_id']
        db.delete_unique(u'm4change_mcctstatus', ['form_id'])

        # Deleting field 'McctStatus.received_on'
        db.delete_column(u'm4change_mcctstatus', 'received_on')

        # Deleting field 'McctStatus.registration_date'
        db.delete_column(u'm4change_mcctstatus', 'registration_date')

        # Deleting field 'McctStatus.immunized'
        db.delete_column(u'm4change_mcctstatus', 'immunized')

        # Deleting field 'McctStatus.is_booking'
        db.delete_column(u'm4change_mcctstatus', 'is_booking')


    models = {
        u'm4change.mcctstatus': {
            'Meta': {'object_name': 'McctStatus'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'immunized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_booking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'received_on': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'registration_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['m4change']
