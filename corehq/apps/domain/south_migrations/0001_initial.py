# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'TransferDomainRequest'
        db.create_table(u'domain_transferdomainrequest', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('request_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('request_ip', self.gf('django.db.models.fields.CharField')(max_length=80, null=True, blank=True)),
            ('confirm_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('confirm_ip', self.gf('django.db.models.fields.CharField')(max_length=80, null=True, blank=True)),
            ('transfer_guid', self.gf('django.db.models.fields.CharField')(max_length=32, null=True, blank=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('from_username', self.gf('django.db.models.fields.CharField')(max_length=80)),
            ('to_username', self.gf('django.db.models.fields.CharField')(max_length=80)),
        ))
        db.send_create_signal(u'domain', ['TransferDomainRequest'])


    def backwards(self, orm):
        
        # Deleting model 'TransferDomainRequest'
        db.delete_table(u'domain_transferdomainrequest')


    models = {
        u'domain.transferdomainrequest': {
            'Meta': {'object_name': 'TransferDomainRequest'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'confirm_ip': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'confirm_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'from_username': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'request_ip': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True', 'blank': 'True'}),
            'request_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'to_username': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'transfer_guid': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['domain']
