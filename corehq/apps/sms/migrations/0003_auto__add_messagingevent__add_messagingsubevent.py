# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'MessagingEvent'
        db.create_table('sms_messagingevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=255, null=False, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(null=False, db_index=True)),
            ('source', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('source_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('content_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('form_unique_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('error_code', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('recipient_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=True, db_index=True)),
            ('recipient_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
        ))
        db.send_create_signal('sms', ['MessagingEvent'])

        # Adding model 'MessagingSubEvent'
        db.create_table('sms_messagingsubevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['sms.MessagingEvent'])),
            ('recipient_type', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('recipient_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('case_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=3, null=False)),
            ('error_code', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
        ))
        db.send_create_signal('sms', ['MessagingSubEvent'])

    def backwards(self, orm):
        
        # Deleting model 'MessagingEvent'
        db.delete_table('sms_messagingevent')

        # Deleting model 'MessagingSubEvent'
        db.delete_table('sms_messagingsubevent')

    models = {
        'sms.phonenumber': {
            'Meta': {'object_name': 'PhoneNumber'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True', 'null': 'False', 'db_index': 'True'}),
            'send_sms': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'send_ivr': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'can_opt_in': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
        },
        'sms.messagingevent': {
            'Meta': {'object_name': 'MessagingEvent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'False', 'db_index': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'False', 'db_index': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'source_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'content_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'form_unique_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'error_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'recipient_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'db_index': 'True'}),
            'recipient_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
        },
        'sms.messagingsubevent': {
            'Meta': {'object_name': 'MessagingSubEvent'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sms.MessagingEvent']"}),
            'recipient_type': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'recipient_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'case_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'False'}),
            'error_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
        },
    }

    complete_apps = ['sms']
