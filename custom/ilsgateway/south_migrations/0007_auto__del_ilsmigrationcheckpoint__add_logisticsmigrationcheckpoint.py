# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Deleting model 'ILSMigrationCheckpoint'
        db.delete_table(u'ilsgateway_ilsmigrationcheckpoint')

        # Adding model 'LogisticsMigrationCheckpoint'
        db.create_table(u'ilsgateway_logisticsmigrationcheckpoint', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('start_date', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('api', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('limit', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('offset', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'ilsgateway', ['LogisticsMigrationCheckpoint'])


    def backwards(self, orm):
        
        # Adding model 'ILSMigrationCheckpoint'
        db.create_table(u'ilsgateway_ilsmigrationcheckpoint', (
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('limit', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('offset', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('api', self.gf('django.db.models.fields.CharField')(max_length=100)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start_date', self.gf('django.db.models.fields.DateTimeField')(null=True)),
        ))
        db.send_create_signal(u'ilsgateway', ['ILSMigrationCheckpoint'])

        # Deleting model 'LogisticsMigrationCheckpoint'
        db.delete_table(u'ilsgateway_logisticsmigrationcheckpoint')


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
            'report_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2014, 11, 12, 13, 33, 1, 250544)'}),
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
        u'ilsgateway.historicallocationgroup': {
            'Meta': {'unique_together': "(('location_id', 'date', 'group'),)", 'object_name': 'HistoricalLocationGroup'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'group': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location_id': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['locations.SQLLocation']"})
        },
        u'ilsgateway.logisticsmigrationcheckpoint': {
            'Meta': {'object_name': 'LogisticsMigrationCheckpoint'},
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
        },
        u'locations.sqllocation': {
            'Meta': {'unique_together': "(('domain', 'site_code'),)", 'object_name': 'SQLLocation'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            'location_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'longitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            'metadata': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': u"orm['locations.SQLLocation']"}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'site_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'supply_point_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'db_index': 'True'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['ilsgateway']
