# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    needed_by = (
        ("smsbillables", "0001_initial"),
    )

    def forwards(self, orm):
        
        # Adding model 'Currency'
        db.create_table(u'accounting_currency', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=3)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=25, db_index=True)),
            ('symbol', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('rate_to_default', self.gf('django.db.models.fields.DecimalField')(default=1.0, max_digits=20, decimal_places=9)),
            ('date_updated', self.gf('django.db.models.fields.DateField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal(u'accounting', ['Currency'])


    def backwards(self, orm):
        
        # Deleting model 'Currency'
        db.delete_table(u'accounting_currency')


    models = {
        u'accounting.currency': {
            'Meta': {'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'date_updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_index': 'True'}),
            'rate_to_default': ('django.db.models.fields.DecimalField', [], {'default': '1.0', 'max_digits': '20', 'decimal_places': '9'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['accounting']
