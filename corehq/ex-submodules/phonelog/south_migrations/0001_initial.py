# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Log'
        db.create_table(u'phonelog_log', (
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('msg', self.gf('django.db.models.fields.TextField')()),
            ('id', self.gf('django.db.models.fields.CharField')(max_length=50, primary_key=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('date', self.gf('django.db.models.fields.DateTimeField')()),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('device_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('app_version', self.gf('django.db.models.fields.TextField')()),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal(u'phonelog', ['Log'])

        # Adding model 'UserLog'
        db.create_table(u'phonelog_userlog', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('sync_token', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal(u'phonelog', ['UserLog'])


    def backwards(self, orm):
        
        # Deleting model 'Log'
        db.delete_table(u'phonelog_log')

        # Deleting model 'UserLog'
        db.delete_table(u'phonelog_userlog')


    models = {
        u'phonelog.log': {
            'Meta': {'object_name': 'Log'},
            'app_version': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'msg': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'phonelog.userlog': {
            'Meta': {'object_name': 'UserLog'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sync_token': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        }
    }

    complete_apps = ['phonelog']
