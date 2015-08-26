# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding index on 'UserLog', fields ['username']
        db.create_index(u'phonelog_userlog', ['username'])

        # Adding index on 'UserLog', fields ['xform_id']
        db.create_index(u'phonelog_userlog', ['xform_id'])

        # Adding index on 'Log', fields ['username']
        db.create_index(u'phonelog_log', ['username'])

        # Adding index on 'Log', fields ['xform_id']
        db.create_index(u'phonelog_log', ['xform_id'])

        # Adding index on 'Log', fields ['domain']
        db.create_index(u'phonelog_log', ['domain'])

        # Adding index on 'Log', fields ['date']
        db.create_index(u'phonelog_log', ['date'])

        # Adding index on 'Log', fields ['type']
        db.create_index(u'phonelog_log', ['type'])

        # Adding index on 'Log', fields ['device_id']
        db.create_index(u'phonelog_log', ['device_id'])


    def backwards(self, orm):
        
        # Removing index on 'Log', fields ['device_id']
        db.delete_index(u'phonelog_log', ['device_id'])

        # Removing index on 'Log', fields ['type']
        db.delete_index(u'phonelog_log', ['type'])

        # Removing index on 'Log', fields ['date']
        db.delete_index(u'phonelog_log', ['date'])

        # Removing index on 'Log', fields ['domain']
        db.delete_index(u'phonelog_log', ['domain'])

        # Removing index on 'Log', fields ['xform_id']
        db.delete_index(u'phonelog_log', ['xform_id'])

        # Removing index on 'Log', fields ['username']
        db.delete_index(u'phonelog_log', ['username'])

        # Removing index on 'UserLog', fields ['xform_id']
        db.delete_index(u'phonelog_userlog', ['xform_id'])

        # Removing index on 'UserLog', fields ['username']
        db.delete_index(u'phonelog_userlog', ['username'])


    models = {
        u'phonelog.log': {
            'Meta': {'object_name': 'Log'},
            'app_version': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'msg': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        },
        u'phonelog.userlog': {
            'Meta': {'object_name': 'UserLog'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sync_token': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        }
    }

    complete_apps = ['phonelog']
