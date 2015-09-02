# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'OwnershipCleanlinessFlag'
        db.create_table(u'phone_ownershipcleanlinessflag', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('owner_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('is_clean', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('last_checked', self.gf('django.db.models.fields.DateTimeField')()),
            ('hint', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal(u'phone', ['OwnershipCleanlinessFlag'])

        # Adding unique constraint on 'OwnershipCleanlinessFlag', fields ['domain', 'owner_id']
        db.create_unique(u'phone_ownershipcleanlinessflag', ['domain', 'owner_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'OwnershipCleanlinessFlag', fields ['domain', 'owner_id']
        db.delete_unique(u'phone_ownershipcleanlinessflag', ['domain', 'owner_id'])

        # Deleting model 'OwnershipCleanlinessFlag'
        db.delete_table(u'phone_ownershipcleanlinessflag')


    models = {
        u'phone.ownershipcleanlinessflag': {
            'Meta': {'unique_together': "[('domain', 'owner_id')]", 'object_name': 'OwnershipCleanlinessFlag'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'hint': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_clean': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_checked': ('django.db.models.fields.DateTimeField', [], {}),
            'owner_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        }
    }

    complete_apps = ['phone']
