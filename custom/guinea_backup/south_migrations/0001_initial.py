# -*- coding: utf-8 -*-
from datetime import date
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from custom.guinea_backup.models import BackupRecord


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'BackupRecord'
        db.create_table(u'guinea_backup_backuprecord', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('last_update', self.gf('django.db.models.fields.DateField')()),
        ))
        db.send_create_signal(u'guinea_backup', ['BackupRecord'])

        #Create a dummy record to seed the db with something far enough back
        dummy = BackupRecord(last_update=date(2014, 01, 01))
        dummy.save()

    def backwards(self, orm):
        # Deleting model 'BackupRecord'
        db.delete_table(u'guinea_backup_backuprecord')

    models = {
        u'guinea_backup.backuprecord': {
            'Meta': {'object_name': 'BackupRecord'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_update': ('django.db.models.fields.DateField', [], {})
        }
    }

    complete_apps = ['guinea_backup']
