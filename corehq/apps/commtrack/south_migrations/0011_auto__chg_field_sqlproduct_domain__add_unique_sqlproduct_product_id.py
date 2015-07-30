# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding unique constraint on 'SQLProduct', fields ['product_id']
        db.create_unique(u'commtrack_sqlproduct', ['product_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'SQLProduct', fields ['product_id']
        db.delete_unique(u'commtrack_sqlproduct', ['product_id'])


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
            'product_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
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
