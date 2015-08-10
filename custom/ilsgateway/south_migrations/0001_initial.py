# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'ILSMigrationCheckpoint'

        db.create_table(u'ilsgateway_ilsmigrationcheckpoint', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('api', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('limit', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('offset', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'ilsgateway', ['ILSMigrationCheckpoint'])

        # Adding model 'SupplyPointStatus'
        db.create_table(u'ilsgateway_supplypointstatus', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('status_type', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('status_value', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('status_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
        ))
        db.send_create_signal(u'ilsgateway', ['SupplyPointStatus'])

        # Adding model 'DeliveryGroupReport'
        db.create_table(u'ilsgateway_deliverygroupreport', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('supply_point', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')()),
            ('report_date',
             self.gf('django.db.models.fields.DateTimeField')
             (
                 default=datetime.datetime(2014, 10, 1, 9, 15, 49, 89325),
                 auto_now_add=True, blank=True
             )),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('delivery_group', self.gf('django.db.models.fields.CharField')(max_length=1)),
        ))
        db.send_create_signal(u'ilsgateway', ['DeliveryGroupReport'])

    def backwards(self, orm):
        
        # Deleting model 'ILSMigrationCheckpoint'
        db.delete_table(u'ilsgateway_ilsmigrationcheckpoint')

        # Deleting model 'SupplyPointStatus'
        db.delete_table(u'ilsgateway_supplypointstatus')

        # Deleting model 'DeliveryGroupReport'
        db.delete_table(u'ilsgateway_deliverygroupreport')

    models = {
        u'ilsgateway.deliverygroupreport': {
            'Meta': {'ordering': "('-report_date',)", 'object_name': 'DeliveryGroupReport'},
            'delivery_group': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {}),
            'report_date': ('django.db.models.fields.DateTimeField', [],
                            {'default': 'datetime.datetime(2014, 10, 1, 9, 15, 49, 89325)',
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
            'offset': ('django.db.models.fields.PositiveIntegerField', [], {})
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
