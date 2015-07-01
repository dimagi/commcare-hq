# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing index on 'DeviceReportEntry', fields ['username']
        db.delete_index(u'phonelog_devicereportentry', ['username'])

        # Removing index on 'DeviceReportEntry', fields ['user_id']
        db.delete_index(u'phonelog_devicereportentry', ['user_id'])

        # Removing index on 'DeviceReportEntry', fields ['date']
        db.delete_index(u'phonelog_devicereportentry', ['date'])

        # Removing index on 'DeviceReportEntry', fields ['type']
        db.delete_index(u'phonelog_devicereportentry', ['type'])

        # Removing index on 'DeviceReportEntry', fields ['device_id']
        db.delete_index(u'phonelog_devicereportentry', ['device_id'])

        # Adding index on 'DeviceReportEntry', fields ['domain', 'type', 'date']
        db.create_index(u'phonelog_devicereportentry', ['domain', 'type', 'date'])

        # Adding index on 'DeviceReportEntry', fields ['domain', 'date']
        db.create_index(u'phonelog_devicereportentry', ['domain', 'date'])

        # Adding index on 'DeviceReportEntry', fields ['domain', 'device_id', 'date']
        db.create_index(u'phonelog_devicereportentry', ['domain', 'device_id', 'date'])

        # Adding index on 'DeviceReportEntry', fields ['domain', 'username', 'date']
        db.create_index(u'phonelog_devicereportentry', ['domain', 'username', 'date'])

        # Adding index on 'DeviceReportEntry', fields ['domain', 'user_id', 'date']
        db.create_index(u'phonelog_devicereportentry', ['domain', 'user_id', 'date'])


    def backwards(self, orm):
        # Removing index on 'DeviceReportEntry', fields ['domain', 'user_id', 'date']
        db.delete_index(u'phonelog_devicereportentry', ['domain', 'user_id', 'date'])

        # Removing index on 'DeviceReportEntry', fields ['domain', 'username', 'date']
        db.delete_index(u'phonelog_devicereportentry', ['domain', 'username', 'date'])

        # Removing index on 'DeviceReportEntry', fields ['domain', 'device_id', 'date']
        db.delete_index(u'phonelog_devicereportentry', ['domain', 'device_id', 'date'])

        # Removing index on 'DeviceReportEntry', fields ['domain', 'date']
        db.delete_index(u'phonelog_devicereportentry', ['domain', 'date'])

        # Removing index on 'DeviceReportEntry', fields ['domain', 'type', 'date']
        db.delete_index(u'phonelog_devicereportentry', ['domain', 'type', 'date'])

        # Adding index on 'DeviceReportEntry', fields ['device_id']
        db.create_index(u'phonelog_devicereportentry', ['device_id'])

        # Adding index on 'DeviceReportEntry', fields ['type']
        db.create_index(u'phonelog_devicereportentry', ['type'])

        # Adding index on 'DeviceReportEntry', fields ['date']
        db.create_index(u'phonelog_devicereportentry', ['date'])

        # Adding index on 'DeviceReportEntry', fields ['user_id']
        db.create_index(u'phonelog_devicereportentry', ['user_id'])

        # Adding index on 'DeviceReportEntry', fields ['username']
        db.create_index(u'phonelog_devicereportentry', ['username'])


    models = {
        u'phonelog.devicereportentry': {
            'Meta': {'unique_together': "[('xform_id', 'i')]", 'object_name': 'DeviceReportEntry', 'index_together': "[('domain', 'date'), ('domain', 'type', 'date'), ('domain', 'device_id', 'date'), ('domain', 'username', 'date'), ('domain', 'user_id', 'date')]"},
            'app_version': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'i': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'msg': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        },
        u'phonelog.userentry': {
            'Meta': {'unique_together': "[('xform_id', 'i')]", 'object_name': 'UserEntry'},
            'i': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sync_token': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        }
    }

    complete_apps = ['phonelog']