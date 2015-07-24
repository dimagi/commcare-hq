# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'DropboxUploadHelper'
        db.create_table(u'dropbox_dropboxuploadhelper', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dest', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('src', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('progress', self.gf('django.db.models.fields.DecimalField')(default=0, max_digits=3, decimal_places=2)),
            ('download_id', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('failure_reason', self.gf('django.db.models.fields.CharField')(default=None, max_length=255, null=True)),
        ))
        db.send_create_signal(u'dropbox', ['DropboxUploadHelper'])


    def backwards(self, orm):
        # Deleting model 'DropboxUploadHelper'
        db.delete_table(u'dropbox_dropboxuploadhelper')


    models = {
        u'dropbox.dropboxuploadhelper': {
            'Meta': {'object_name': 'DropboxUploadHelper'},
            'dest': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'download_id': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'failure_reason': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'progress': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '3', 'decimal_places': '2'}),
            'src': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['dropbox']