# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'TimezoneMigrationProgress'
        db.create_table(u'tzmigration_timezonemigrationprogress', (
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=256, primary_key=True, db_index=True)),
            ('migration_status', self.gf('django.db.models.fields.CharField')(default='not_started', max_length=11)),
        ))
        db.send_create_signal(u'tzmigration', ['TimezoneMigrationProgress'])


    def backwards(self, orm):
        
        # Deleting model 'TimezoneMigrationProgress'
        db.delete_table(u'tzmigration_timezonemigrationprogress')


    models = {
        u'tzmigration.timezonemigrationprogress': {
            'Meta': {'object_name': 'TimezoneMigrationProgress'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256', 'primary_key': 'True', 'db_index': 'True'}),
            'migration_status': ('django.db.models.fields.CharField', [], {'default': "'not_started'", 'max_length': '11'})
        }
    }

    complete_apps = ['tzmigration']
