# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'SQLProduct.code'
        db.add_column(u'commtrack_sqlproduct', 'code', self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True), keep_default=False)

        # Adding field 'SQLProduct.description'
        db.add_column(u'commtrack_sqlproduct', 'description', self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True), keep_default=False)

        # Adding field 'SQLProduct.category'
        db.add_column(u'commtrack_sqlproduct', 'category', self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True), keep_default=False)

        # Adding field 'SQLProduct.program_id'
        db.add_column(u'commtrack_sqlproduct', 'program_id', self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True), keep_default=False)

        # Adding field 'SQLProduct.cost'
        db.add_column(u'commtrack_sqlproduct', 'cost', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=5), keep_default=False)

        # Adding field 'SQLProduct.product_data'
        db.add_column(u'commtrack_sqlproduct', 'product_data', self.gf('json_field.fields.JSONField')(default={}), keep_default=False)

        # Adding field 'SQLProduct.units'
        db.add_column(u'commtrack_sqlproduct', 'units', self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'SQLProduct.code'
        db.delete_column(u'commtrack_sqlproduct', 'code')

        # Deleting field 'SQLProduct.description'
        db.delete_column(u'commtrack_sqlproduct', 'description')

        # Deleting field 'SQLProduct.category'
        db.delete_column(u'commtrack_sqlproduct', 'category')

        # Deleting field 'SQLProduct.program_id'
        db.delete_column(u'commtrack_sqlproduct', 'program_id')

        # Deleting field 'SQLProduct.cost'
        db.delete_column(u'commtrack_sqlproduct', 'cost')

        # Deleting field 'SQLProduct.product_data'
        db.delete_column(u'commtrack_sqlproduct', 'product_data')

        # Deleting field 'SQLProduct.units'
        db.delete_column(u'commtrack_sqlproduct', 'units')


    models = {
        u'commtrack.sqlproduct': {
            'Meta': {'object_name': 'SQLProduct'},
            'category': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'code': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'cost': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            'description': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'units': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'product_data': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'program_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'})
        },
        u'commtrack.stockstate': {
            'Meta': {'unique_together': "(('section_id', 'case_id', 'product_id'),)", 'object_name': 'StockState'},
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'daily_consumption': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified_date': ('django.db.models.fields.DateTimeField', [], {}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'section_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'sql_product': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['commtrack.SQLProduct']"}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'default': "'0'", 'max_digits': '20', 'decimal_places': '5'})
        }
    }

    complete_apps = ['commtrack']
