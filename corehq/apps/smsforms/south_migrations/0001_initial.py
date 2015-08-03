# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'SQLXFormsSession'
        db.create_table(u'smsforms_sqlxformssession', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('couch_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('connection_id', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=50, null=True, blank=True)),
            ('session_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('form_xmlns', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')()),
            ('modified_time', self.gf('django.db.models.fields.DateTimeField')()),
            ('end_time', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('completed', self.gf('django.db.models.fields.BooleanField')()),
            ('domain', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=100, null=True, blank=True)),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('app_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('submission_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('survey_incentive', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('session_type', self.gf('django.db.models.fields.CharField')(default='SMS', max_length=10)),
            ('workflow', self.gf('django.db.models.fields.CharField')(max_length=20, null=True, blank=True)),
            ('reminder_id', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
        ))
        db.send_create_signal(u'smsforms', ['SQLXFormsSession'])


    def backwards(self, orm):
        
        # Deleting model 'SQLXFormsSession'
        db.delete_table(u'smsforms_sqlxformssession')


    models = {
        u'smsforms.sqlxformssession': {
            'Meta': {'object_name': 'SQLXFormsSession'},
            'app_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'completed': ('django.db.models.fields.BooleanField', [], {}),
            'connection_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'couch_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'form_xmlns': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified_time': ('django.db.models.fields.DateTimeField', [], {}),
            'reminder_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'session_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'session_type': ('django.db.models.fields.CharField', [], {'default': "'SMS'", 'max_length': '10'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {}),
            'submission_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'survey_incentive': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['smsforms']
