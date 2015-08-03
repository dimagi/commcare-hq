# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'DeviceReportEntry.server_date'
        db.add_column(u'phonelog_devicereportentry', 'server_date', self.gf('django.db.models.fields.DateTimeField')(null=True, db_index=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'DeviceReportEntry.server_date'
        db.delete_column(u'phonelog_devicereportentry', 'server_date')


    models = {
        u'phonelog.devicereportentry': {
            'Meta': {'unique_together': "[('xform_id', 'i')]", 'object_name': 'DeviceReportEntry'},
            'app_version': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'i': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'msg': ('django.db.models.fields.TextField', [], {}),
            'server_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'db_index': 'True'}),
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
