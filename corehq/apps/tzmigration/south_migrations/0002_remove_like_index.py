# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        db.execute("DROP INDEX IF EXISTS tzmigration_timezonemigrationprogress_domain_like")

    def backwards(self, orm):
        # don't add it back
        pass

    models = {
        u'tzmigration.timezonemigrationprogress': {
            'Meta': {'object_name': 'TimezoneMigrationProgress'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'primary_key': 'True', 'db_index': 'True'}),
            'migration_status': ('django.db.models.fields.CharField', [], {'default': "'not_started'", 'max_length': '11'})
        }
    }

    complete_apps = ['tzmigration']
