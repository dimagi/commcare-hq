# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'OrganizationSummary'
        db.create_table(u'ilsgateway_organizationsummary', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('external_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('total_orgs', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('average_lead_time_in_days', self.gf('django.db.models.fields.FloatField')(default=0)),
        ))
        db.send_create_signal(u'ilsgateway', ['OrganizationSummary'])

        # Adding model 'ProductAvailabilityData'
        db.create_table(u'ilsgateway_productavailabilitydata', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('external_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('product', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('total', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('with_stock', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('without_stock', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('without_data', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
        ))
        db.send_create_signal(u'ilsgateway', ['ProductAvailabilityData'])

        # Adding model 'SupplyPointWarehouseRecord'
        db.create_table(u'ilsgateway_supplypointwarehouserecord', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'ilsgateway', ['SupplyPointWarehouseRecord'])

        # Adding model 'Alert'
        db.create_table(u'ilsgateway_alert', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('update_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('external_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('number', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('text', self.gf('django.db.models.fields.TextField')()),
            ('url', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'ilsgateway', ['Alert'])

        # Adding model 'GroupSummary'
        db.create_table(u'ilsgateway_groupsummary', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('org_summary',
             self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ilsgateway.OrganizationSummary'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('total', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('responded', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('on_time', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('complete', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('external_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
        ))
        db.send_create_signal(u'ilsgateway', ['GroupSummary'])

        # Adding field 'DeliveryGroupReport.external_id'
        db.add_column(u'ilsgateway_deliverygroupreport', 'external_id',
                      self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True),
                      keep_default=False)

        # Changing field 'DeliveryGroupReport.report_date'
        db.alter_column(u'ilsgateway_deliverygroupreport', 'report_date',
                        self.gf('django.db.models.fields.DateTimeField')())

        # Adding field 'SupplyPointStatus.external_id'
        db.add_column(u'ilsgateway_supplypointstatus', 'external_id',
                      self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True),
                      keep_default=False)

    def backwards(self, orm):
        
        # Deleting model 'OrganizationSummary'
        db.delete_table(u'ilsgateway_organizationsummary')

        # Deleting model 'ProductAvailabilityData'
        db.delete_table(u'ilsgateway_productavailabilitydata')

        # Deleting model 'SupplyPointWarehouseRecord'
        db.delete_table(u'ilsgateway_supplypointwarehouserecord')

        # Deleting model 'Alert'
        db.delete_table(u'ilsgateway_alert')

        # Deleting model 'GroupSummary'
        db.delete_table(u'ilsgateway_groupsummary')

        # Deleting field 'DeliveryGroupReport.external_id'
        db.delete_column(u'ilsgateway_deliverygroupreport', 'external_id')

        # Changing field 'DeliveryGroupReport.report_date'
        db.alter_column(u'ilsgateway_deliverygroupreport', 'report_date',
                        self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True))

        # Deleting field 'SupplyPointStatus.external_id'
        db.delete_column(u'ilsgateway_supplypointstatus', 'external_id')

    models = {
        u'ilsgateway.alert': {
            'Meta': {'object_name': 'Alert'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'expires': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True',
                                                               'blank': 'True'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True',
                                                              'blank': 'True'})
        },
        u'ilsgateway.deliverygroupreport': {
            'Meta': {'ordering': "('-report_date',)", 'object_name': 'DeliveryGroupReport'},
            'delivery_group': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'report_date': ('django.db.models.fields.DateTimeField', [],
                            {'default': 'datetime.datetime(2014, 10, 16, 9, 25, 21, 907582)'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        u'ilsgateway.groupsummary': {
            'Meta': {'object_name': 'GroupSummary'},
            'complete': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'on_time': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'org_summary': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['ilsgateway.OrganizationSummary']"}),
            'responded': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True',
                                                                'blank': 'True'}),
            'total': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        u'ilsgateway.ilsmigrationcheckpoint': {
            'Meta': {'object_name': 'ILSMigrationCheckpoint'},
            'api': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'limit': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'offset': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        u'ilsgateway.organizationsummary': {
            'Meta': {'object_name': 'OrganizationSummary'},
            'average_lead_time_in_days': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'total_orgs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'ilsgateway.productavailabilitydata': {
            'Meta': {'object_name': 'ProductAvailabilityData'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'supply_point': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'total': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'update_date': ('django.db.models.fields.DateTimeField', [], {}),
            'with_stock': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'without_data': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'without_stock': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        u'ilsgateway.supplypointstatus': {
            'Meta': {'ordering': "('-status_date',)", 'object_name': 'SupplyPointStatus'},
            'external_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True',
                                                                                 'db_index': 'True'}),
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
