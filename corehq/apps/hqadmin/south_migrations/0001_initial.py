# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'PillowCheckpointSeqStore'
        db.create_table(u'hqadmin_pillowcheckpointseqstore', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('seq', self.gf('django.db.models.fields.TextField')()),
            ('checkpoint_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('date_updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal(u'hqadmin', ['PillowCheckpointSeqStore'])


    def backwards(self, orm):
        # Deleting model 'PillowCheckpointSeqStore'
        db.delete_table(u'hqadmin_pillowcheckpointseqstore')


    models = {
        u'hqadmin.pillowcheckpointseqstore': {
            'Meta': {'object_name': 'PillowCheckpointSeqStore'},
            'checkpoint_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'date_updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'seq': ('django.db.models.fields.TextField', [], {})
        }
    }

    complete_apps = ['hqadmin']