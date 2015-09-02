# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'MALTRow'
        db.create_table(u'data_analytics_maltrow', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('month', self.gf('django.db.models.fields.DateField')(db_index=True)),
            ('user_id', self.gf('django.db.models.fields.TextField')()),
            ('username', self.gf('django.db.models.fields.TextField')()),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('is_web_user', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('domain_name', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('num_of_forms', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('app_id', self.gf('django.db.models.fields.TextField')()),
            ('is_app_deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('wam', self.gf('django.db.models.fields.NullBooleanField')(default=None, null=True, blank=True)),
            ('pam', self.gf('django.db.models.fields.NullBooleanField')(default=None, null=True, blank=True)),
        ))
        db.send_create_signal(u'data_analytics', ['MALTRow'])

        # Adding unique constraint on 'MALTRow', fields ['month', 'domain_name', 'user_id', 'app_id']
        db.create_unique(u'data_analytics_maltrow', ['month', 'domain_name', 'user_id', 'app_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'MALTRow', fields ['month', 'domain_name', 'user_id', 'app_id']
        db.delete_unique(u'data_analytics_maltrow', ['month', 'domain_name', 'user_id', 'app_id'])

        # Deleting model 'MALTRow'
        db.delete_table(u'data_analytics_maltrow')


    models = {
        u'data_analytics.maltrow': {
            'Meta': {'unique_together': "(('month', 'domain_name', 'user_id', 'app_id'),)", 'object_name': 'MALTRow'},
            'app_id': ('django.db.models.fields.TextField', [], {}),
            'domain_name': ('django.db.models.fields.TextField', [], {'db_index': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_app_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_web_user': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'month': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'num_of_forms': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'pam': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.TextField', [], {}),
            'username': ('django.db.models.fields.TextField', [], {}),
            'wam': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['data_analytics']