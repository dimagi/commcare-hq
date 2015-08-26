# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'ILSMigrationCheckpoint.start_date'
        db.add_column(u'ilsgateway_ilsmigrationcheckpoint', 'start_date',
                      self.gf('django.db.models.fields.DateTimeField')(null=True), keep_default=False)

    def backwards(self, orm):
        
        # Deleting field 'ILSMigrationCheckpoint.start_date'
        db.delete_column(u'ilsgateway_ilsmigrationcheckpoint', 'start_date')

    models = {
        u'ilsgateway.deliverygroupreport': {
            'Meta': {'ordering': "('-report_date',)", 'object_name': 'DeliveryGroupReport'},
            'delivery_group': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'report_date': ('django.db.models.fields.DateTimeField', [],
                            {'default': 'datetime.datetime(2014, 10, 20, 6, 29, 28, 283536)',
                             'auto_now_add': 'True', 'blank': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        u'ilsgateway.ilsmigrationcheckpoint': {
            'Meta': {'object_name': 'ILSMigrationCheckpoint'},
            'api': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'limit': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'offset': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        u'ilsgateway.supplypointstatus': {
            'Meta': {'ordering': "('-status_date',)", 'object_name': 'SupplyPointStatus'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'status_type': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'status_value': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        }
    }

    complete_apps = ['ilsgateway']
