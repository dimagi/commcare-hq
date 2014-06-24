# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'PaymentTracking'
        db.create_table(u'intrahealth_paymenttracking', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('month', self.gf('django.db.models.fields.IntegerField')()),
            ('year', self.gf('django.db.models.fields.IntegerField')()),
            ('calculated_amount_owed', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('actual_amount_owed', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('amount_paid', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'intrahealth', ['PaymentTracking'])


    def backwards(self, orm):
        
        # Deleting model 'PaymentTracking'
        db.delete_table(u'intrahealth_paymenttracking')


    models = {
        u'intrahealth.paymenttracking': {
            'Meta': {'object_name': 'PaymentTracking'},
            'actual_amount_owed': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'amount_paid': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'calculated_amount_owed': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'month': ('django.db.models.fields.IntegerField', [], {}),
            'year': ('django.db.models.fields.IntegerField', [], {})
        }
    }

    complete_apps = ['intrahealth']
