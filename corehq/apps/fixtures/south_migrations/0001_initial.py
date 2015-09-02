# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'UserFixtureStatus'
        db.create_table(u'fixtures_userfixturestatus', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('fixture_type', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('last_modified', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'fixtures', ['UserFixtureStatus'])

        # Adding unique constraint on 'UserFixtureStatus', fields ['user_id', 'fixture_type']
        db.create_unique(u'fixtures_userfixturestatus', ['user_id', 'fixture_type'])


    def backwards(self, orm):
        # Removing unique constraint on 'UserFixtureStatus', fields ['user_id', 'fixture_type']
        db.delete_unique(u'fixtures_userfixturestatus', ['user_id', 'fixture_type'])

        # Deleting model 'UserFixtureStatus'
        db.delete_table(u'fixtures_userfixturestatus')


    models = {
        u'fixtures.userfixturestatus': {
            'Meta': {'unique_together': "(('user_id', 'fixture_type'),)", 'object_name': 'UserFixtureStatus'},
            'fixture_type': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        }
    }

    complete_apps = ['fixtures']