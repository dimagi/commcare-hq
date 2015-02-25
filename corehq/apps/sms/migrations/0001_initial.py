# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'PhoneNumber'
        db.create_table('sms_phonenumber', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('phone_number', self.gf('django.db.models.fields.CharField')(max_length=30, unique=True, null=False, db_index=True)),
            ('send_sms', self.gf('django.db.models.fields.BooleanField')(null=False, default=True)),
            ('send_ivr', self.gf('django.db.models.fields.BooleanField')(null=False, default=True)),
            ('can_opt_in', self.gf('django.db.models.fields.BooleanField')(null=False, default=True)),
        ))
        db.send_create_signal('sms', ['PhoneNumber'])

    def backwards(self, orm):
        
        # Deleting model 'PhoneNumber'
        db.delete_table('sms_phonenumber')

    models = {
        'sms.phonenumber': {
            'Meta': {'object_name': 'PhoneNumber'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True', 'null': 'False', 'db_index': 'True'}),
            'send_sms': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'send_ivr': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
            'can_opt_in': ('django.db.models.fields.BooleanField', [], {'null': 'False', 'default': 'True'}),
        },
    }

    complete_apps = ['sms']
