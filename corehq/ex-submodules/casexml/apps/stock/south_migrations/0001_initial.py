# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'StockReport'
        db.create_table(u'stock_stockreport', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('form_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=20)),
        ))
        db.send_create_signal(u'stock', ['StockReport'])

        # Adding model 'StockTransaction'
        db.create_table(u'stock_stocktransaction', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('report', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['stock.StockReport'])),
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('product_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('quantity', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=5)),
            ('stock_on_hand', self.gf('django.db.models.fields.DecimalField')(max_digits=20, decimal_places=5)),
        ))
        db.send_create_signal(u'stock', ['StockTransaction'])


    def backwards(self, orm):
        
        # Deleting model 'StockReport'
        db.delete_table(u'stock_stockreport')

        # Deleting model 'StockTransaction'
        db.delete_table(u'stock_stocktransaction')


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
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'max_digits': '20', 'decimal_places': '5'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['stock']
