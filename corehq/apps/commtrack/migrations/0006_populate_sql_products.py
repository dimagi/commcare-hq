# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch import sync_docs
import corehq.apps.commtrack.models as commtrack_models

class Migration(DataMigration):

    def forwards(self, orm):
        # hack to force sync docs before this runs
        sync_docs.sync(commtrack_models, verbosity=2)

        # sync products first

        properties_to_sync = [
            ('product_id', '_id'),
            'domain',
            'name',
            'is_archived',
            ('code', 'code_'),
            'description',
            'category',
            'program_id',
            'cost',
            ('units', 'unit'),
            'product_data',
        ]

        product_ids = [r['id'] for r in Product.get_db().view(
            'commtrack/products',
            reduce=False,
        ).all()]

        for product in iter_docs(Product.get_db(), product_ids):
            sql_product = orm.SQLProduct()

            for prop in properties_to_sync:
                if isinstance(prop, tuple):
                    sql_prop, couch_prop = prop
                else:
                    sql_prop = couch_prop = prop

                if couch_prop in product:
                    setattr(sql_product, sql_prop, product[couch_prop])

            sql_product.save()

        # now update stock states

        for ss in orm.StockState.objects.all():
            ss.sql_product = orm.SQLProduct.objects.get(product_id=ss.product_id)
            ss.save()

    def backwards(self, orm):
        orm.SQLProduct.objects.all().delete()


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
            'sql_product': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['commtrack.SQLProduct']", 'null': 'True'}),
            'stock_on_hand': ('django.db.models.fields.DecimalField', [], {'default': "'0'", 'max_digits': '20', 'decimal_places': '5'})
        }
    }

    complete_apps = ['commtrack']
