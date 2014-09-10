# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'CaseData'
        db.create_table(u'sofabed_casedata', (
            ('case_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255, primary_key=True)),
            ('doc_type', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('closed', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('owner_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('opened_on', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('opened_by', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('closed_on', self.gf('django.db.models.fields.DateTimeField')(null=True, db_index=True)),
            ('closed_by', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
            ('modified_on', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('modified_by', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
            ('server_modified_on', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=512)),
            ('external_id', self.gf('django.db.models.fields.CharField')(max_length=512, null=True)),
        ))
        db.send_create_signal(u'sofabed', ['CaseData'])

        # Adding model 'CaseActionData'
        db.create_table(u'sofabed_caseactiondata', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('case', self.gf('django.db.models.fields.related.ForeignKey')(related_name='actions', to=orm['sofabed.CaseData'])),
            ('index', self.gf('django.db.models.fields.IntegerField')()),
            ('action_type', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('user_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('server_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('xform_id', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('xform_xmlns', self.gf('django.db.models.fields.CharField')(max_length=1000, null=True)),
            ('sync_log_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
        ))
        db.send_create_signal(u'sofabed', ['CaseActionData'])


    def backwards(self, orm):
        
        # Deleting model 'CaseData'
        db.delete_table(u'sofabed_casedata')

        # Deleting model 'CaseActionData'
        db.delete_table(u'sofabed_caseactiondata')


    models = {
        u'sofabed.caseactiondata': {
            'Meta': {'ordering': "['date']", 'object_name': 'CaseActionData'},
            'action_type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'case': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'actions'", 'to': u"orm['sofabed.CaseData']"}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {}),
            'server_date': ('django.db.models.fields.DateTimeField', [], {}),
            'sync_log_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'xform_id': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'xform_xmlns': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True'})
        },
        u'sofabed.casedata': {
            'Meta': {'ordering': "['opened_on']", 'object_name': 'CaseData'},
            'case_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'primary_key': 'True'}),
            'closed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'closed_by': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'closed_on': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'doc_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'modified_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'opened_by': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'opened_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'owner_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'server_modified_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'})
        },
        u'sofabed.formdata': {
            'Meta': {'object_name': 'FormData'},
            'app_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'doc_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'duration': ('django.db.models.fields.IntegerField', [], {}),
            'instance_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'primary_key': 'True'}),
            'received_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_end': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'time_start': ('django.db.models.fields.DateTimeField', [], {}),
            'user_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'xmlns': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'db_index': 'True'})
        }
    }

    complete_apps = ['sofabed']
