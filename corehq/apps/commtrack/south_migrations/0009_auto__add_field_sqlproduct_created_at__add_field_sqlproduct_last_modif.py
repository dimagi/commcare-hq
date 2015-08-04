# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):
    def forwards(self, orm):
        # Adding field 'SQLProduct.created_at'
        db.add_column(u'commtrack_sqlproduct', 'created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, default=datetime.datetime(2014, 9, 15, 21, 48, 56, 807841), blank=True), keep_default=False)

        # Adding field 'SQLProduct.last_modified'
        db.add_column(u'commtrack_sqlproduct', 'last_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, default=datetime.datetime(2014, 9, 15, 21, 49, 6, 227085), blank=True), keep_default=False)

    def backwards(self, orm):
        # Deleting field 'SQLProduct.created_at'
        db.delete_column(u'commtrack_sqlproduct', 'created_at')

        # Deleting field 'SQLProduct.last_modified'
        db.delete_column(u'commtrack_sqlproduct', 'last_modified')

    models = {
        u'commtrack.sqlproduct': {
            'Meta': {'object_name': 'SQLProduct'},
            'category': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'code': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'cost': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'product_data': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'product_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'program_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'units': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'})
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
