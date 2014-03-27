# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Removing unique constraint on 'StockState', fields ['section_id', 'case_id', 'product_id']
        db.delete_unique(u'stock_stockstate', ['section_id', 'case_id', 'product_id'])

        # Deleting model 'StockState'
        db.delete_table(u'stock_stockstate')

        # Adding model 'DocDomainMapping'
        db.create_table(u'stock_docdomainmapping', (
            ('doc_id', self.gf('django.db.models.fields.CharField')(max_length=100, primary_key=True, db_index=True)),
            ('doc_type', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('domain_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal(u'stock', ['DocDomainMapping'])


    def backwards(self, orm):
        
        # Adding model 'StockState'
        db.create_table(u'stock_stockstate', (
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('stock_on_hand', self.gf('django.db.models.fields.DecimalField')(default='0', max_digits=20, decimal_places=5)),
            ('product_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('daily_consumption', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=5)),
            ('last_modified_date', self.gf('django.db.models.fields.DateTimeField')()),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('section_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
        ))
        db.send_create_signal(u'stock', ['StockState'])

        # Adding unique constraint on 'StockState', fields ['section_id', 'case_id', 'product_id']
        db.create_unique(u'stock_stockstate', ['section_id', 'case_id', 'product_id'])

        # Deleting model 'DocDomainMapping'
        db.delete_table(u'stock_docdomainmapping')


    models = {
        u'stock.docdomainmapping': {
            'Meta': {'object_name': 'DocDomainMapping'},
            'doc_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'primary_key': 'True', 'db_index': 'True'}),
            'doc_type': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'domain_name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
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
            'section_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'max_digits': '20', 'decimal_places': '5'}),
            'subtype': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        }
    }

    complete_apps = ['stock']
