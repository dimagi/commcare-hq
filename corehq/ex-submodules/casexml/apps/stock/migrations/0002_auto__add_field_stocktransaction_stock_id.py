# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'StockTransaction.stock_id'
        db.add_column(u'stock_stocktransaction', 'stock_id', self.gf('django.db.models.fields.CharField')(default='stock', max_length=100, db_index=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'StockTransaction.stock_id'
        db.delete_column(u'stock_stocktransaction', 'stock_id')


    models = {
        u'stock.stockreport': {
            'Meta': {'object_name': 'StockReport'},
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'form_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'stock.stocktransaction': {
            'Meta': {'object_name': 'StockTransaction'},
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['stock.StockReport']"}),
            'stock_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'max_digits': '20', 'decimal_places': '5'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['stock']
