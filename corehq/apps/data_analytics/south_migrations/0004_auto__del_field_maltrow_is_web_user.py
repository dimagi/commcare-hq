# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'MALTRow.is_web_user'
        db.delete_column(u'data_analytics_maltrow', 'is_web_user')


    def backwards(self, orm):
        # Adding field 'MALTRow.is_web_user'
        db.add_column(u'data_analytics_maltrow', 'is_web_user',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    models = {
        u'data_analytics.maltrow': {
            'Meta': {'unique_together': "(('month', 'domain_name', 'user_id', 'app_id'),)", 'object_name': 'MALTRow'},
            'app_id': ('django.db.models.fields.TextField', [], {}),
            'domain_name': ('django.db.models.fields.TextField', [], {'db_index': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_app_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'month': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'num_of_forms': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'pam': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.TextField', [], {}),
            'user_type': ('django.db.models.fields.TextField', [], {}),
            'username': ('django.db.models.fields.TextField', [], {}),
            'wam': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['data_analytics']