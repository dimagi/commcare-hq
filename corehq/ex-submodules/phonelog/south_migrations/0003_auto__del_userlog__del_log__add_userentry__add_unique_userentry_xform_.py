# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'UserLog'
        db.delete_table(u'phonelog_userlog')

        # Deleting model 'Log'
        db.delete_table(u'phonelog_log')

        # Adding model 'UserEntry'
        db.create_table(u'phonelog_userentry', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('i', self.gf('django.db.models.fields.IntegerField')()),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('sync_token', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
        ))
        db.send_create_signal(u'phonelog', ['UserEntry'])

        # Adding unique constraint on 'UserEntry', fields ['xform_id', 'i']
        db.create_unique(u'phonelog_userentry', ['xform_id', 'i'])

        # Adding model 'DeviceReportEntry'
        db.create_table(u'phonelog_devicereportentry', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('i', self.gf('django.db.models.fields.IntegerField')()),
            ('msg', self.gf('django.db.models.fields.TextField')()),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('device_id', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('app_version', self.gf('django.db.models.fields.TextField')()),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
        ))
        db.send_create_signal(u'phonelog', ['DeviceReportEntry'])

        # Adding unique constraint on 'DeviceReportEntry', fields ['xform_id', 'i']
        db.create_unique(u'phonelog_devicereportentry', ['xform_id', 'i'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'DeviceReportEntry', fields ['xform_id', 'i']
        db.delete_unique(u'phonelog_devicereportentry', ['xform_id', 'i'])

        # Removing unique constraint on 'UserEntry', fields ['xform_id', 'i']
        db.delete_unique(u'phonelog_userentry', ['xform_id', 'i'])

        # Adding model 'UserLog'
        db.create_table(u'phonelog_userlog', (
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('sync_token', self.gf('django.db.models.fields.CharField')(max_length=50)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'phonelog', ['UserLog'])

        # Adding model 'Log'
        db.create_table(u'phonelog_log', (
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('msg', self.gf('django.db.models.fields.TextField')()),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('app_version', self.gf('django.db.models.fields.TextField')()),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('id', self.gf('django.db.models.fields.CharField')(max_length=50, primary_key=True)),
            ('device_id', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
        ))
        db.send_create_signal(u'phonelog', ['Log'])

        # Deleting model 'UserEntry'
        db.delete_table(u'phonelog_userentry')

        # Deleting model 'DeviceReportEntry'
        db.delete_table(u'phonelog_devicereportentry')


    models = {
        u'phonelog.devicereportentry': {
            'Meta': {'unique_together': "[('xform_id', 'i')]", 'object_name': 'DeviceReportEntry'},
            'app_version': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'i': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'msg': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50'})
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
