# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Changing field 'IncomingRequest.content'
        db.alter_column('telerivet_incomingrequest', 'content', self.gf('django.db.models.fields.TextField')(null=True))

    def backwards(self, orm):
        # Changing field 'IncomingRequest.content'
        db.alter_column('telerivet_incomingrequest', 'content', self.gf('django.db.models.fields.CharField')(max_length=255, null=True))

    models = {
        'telerivet.incomingrequest': {
            'Meta': {'object_name': 'IncomingRequest'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'event': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'message_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'content': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'from_number': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'from_number_e164': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'to_number': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'time_created': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'time_sent': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'contact_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'phone_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'service_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'project_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
        },
    }

    complete_apps = ['telerivet']
