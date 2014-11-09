# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'ReportRun'
        db.create_table(u'ilsgateway_reportrun', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start', self.gf('django.db.models.fields.DateTimeField')()),
            ('end', self.gf('django.db.models.fields.DateTimeField')()),
            ('start_run', self.gf('django.db.models.fields.DateTimeField')()),
            ('end_run', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('complete', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_error', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=60)),
        ))
        db.send_create_signal(u'ilsgateway', ['ReportRun'])


    def backwards(self, orm):
        
        # Deleting model 'ReportRun'
        db.delete_table(u'ilsgateway_reportrun')


    models = {
        u'ilsgateway.alert': {
            'Meta': {'object_name': 'Alert'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'expires': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        u'ilsgateway.deliverygroupreport': {
            'Meta': {'ordering': "('-report_date',)", 'object_name': 'DeliveryGroupReport'},
            'delivery_group': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'report_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2014, 10, 24, 6, 17, 1, 956481)'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        u'ilsgateway.groupsummary': {
            'Meta': {'object_name': 'GroupSummary'},
            'complete': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'on_time': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'org_summary': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ilsgateway.OrganizationSummary']"}),
            'responded': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'total': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
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
        u'ilsgateway.organizationsummary': {
            'Meta': {'object_name': 'OrganizationSummary'},
            'average_lead_time_in_days': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'total_orgs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'ilsgateway.productavailabilitydata': {
            'Meta': {'object_name': 'ProductAvailabilityData'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'total': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {}),
            'with_stock': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'without_data': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'without_stock': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        u'ilsgateway.reportrun': {
            'Meta': {'object_name': 'ReportRun'},
            'complete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            'end_run': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'has_error': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start': ('django.db.models.fields.DateTimeField', [], {}),
            'start_run': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'ilsgateway.supplypointstatus': {
            'Meta': {'ordering': "('-status_date',)", 'object_name': 'SupplyPointStatus'},
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'status_type': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'status_value': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        u'ilsgateway.supplypointwarehouserecord': {
            'Meta': {'object_name': 'SupplyPointWarehouseRecord'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        }
    }

    complete_apps = ['ilsgateway']
