# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'UserRemoval'
        db.create_table(u'groups_userremoval', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('group_id', self.gf('django.db.models.fields.TextField')()),
            ('user_id', self.gf('django.db.models.fields.TextField')()),
            ('removed_on', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'groups', ['UserRemoval'])

        # Adding unique constraint on 'UserRemoval', fields ['user_id', 'group_id']
        db.create_unique(u'groups_userremoval', ['user_id', 'group_id'])

        # Adding index on 'UserRemoval', fields ['user_id', 'removed_on']
        db.create_index(u'groups_userremoval', ['user_id', 'removed_on'])


    def backwards(self, orm):
        # Removing index on 'UserRemoval', fields ['user_id', 'removed_on']
        db.delete_index(u'groups_userremoval', ['user_id', 'removed_on'])

        # Removing unique constraint on 'UserRemoval', fields ['user_id', 'group_id']
        db.delete_unique(u'groups_userremoval', ['user_id', 'group_id'])

        # Deleting model 'UserRemoval'
        db.delete_table(u'groups_userremoval')


    models = {
        u'groups.userremoval': {
            'Meta': {'unique_together': "(('user_id', 'group_id'),)", 'object_name': 'UserRemoval', 'index_together': "[('user_id', 'removed_on')]"},
            'group_id': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'removed_on': ('django.db.models.fields.DateTimeField', [], {}),
            'user_id': ('django.db.models.fields.TextField', [], {})
        }
    }

    complete_apps = ['groups']