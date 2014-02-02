# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'StockState'
        db.create_table(u'stock_stockstate', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('section_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('product_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('stock_on_hand', self.gf('django.db.models.fields.DecimalField')(default='0', max_digits=20, decimal_places=5)),
            ('daily_consumption', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=5)),
            ('last_modified_date', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'stock', ['StockState'])

        # Adding unique constraint on 'StockState', fields ['section_id', 'case_id', 'product_id']
        db.create_unique(u'stock_stockstate', ['section_id', 'case_id', 'product_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'StockState', fields ['section_id', 'case_id', 'product_id']
        db.delete_unique(u'stock_stockstate', ['section_id', 'case_id', 'product_id'])

        # Deleting model 'StockState'
        db.delete_table(u'stock_stockstate')


    models = {
        u'stock.stockreport': {
            'Meta': {'object_name': 'StockReport'},
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'stock.stockstate': {
            'Meta': {'unique_together': "(('section_id', 'case_id', 'product_id'),)", 'object_name': 'StockState'},
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'daily_consumption': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified_date': ('django.db.models.fields.DateTimeField', [], {}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'section_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'default': "'0'", 'max_digits': '20', 'decimal_places': '5'})
        },
        u'stock.stocktransaction': {
            'Meta': {'object_name': 'StockTransaction'},
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['stock.StockReport']"}),
            'section_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'max_digits': '20', 'decimal_places': '5'}),
            'subtype': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['stock']
