# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Submission'
        db.create_table('receiver_submission', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('submit_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('transaction_uuid', self.gf('django.db.models.fields.CharField')(default='6a8fd8c4-bc5c-11df-8c8b-5cff350164a3', max_length=36)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['domain.Domain'], null=True)),
            ('submit_ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('checksum', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('bytes_received', self.gf('django.db.models.fields.IntegerField')()),
            ('content_type', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('raw_header', self.gf('django.db.models.fields.TextField')()),
            ('raw_post', self.gf('django.db.models.fields.FilePathField')(max_length=255, null=True, match='.*\\.postdata$', path='/home/rowena/workspace/core-hq/data/submissions')),
            ('authenticated_to', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True)),
        ))
        db.send_create_signal('receiver', ['Submission'])

        # Adding model 'Attachment'
        db.create_table('receiver_attachment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('submission', self.gf('django.db.models.fields.related.ForeignKey')(related_name='attachments', to=orm['receiver.Submission'])),
            ('attachment_content_type', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('attachment_uri', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('filepath', self.gf('django.db.models.fields.FilePathField')(path='/home/rowena/workspace/core-hq/data/attachments', max_length=255, match='.*\\.attach$')),
            ('filesize', self.gf('django.db.models.fields.IntegerField')()),
            ('checksum', self.gf('django.db.models.fields.CharField')(max_length=32)),
        ))
        db.send_create_signal('receiver', ['Attachment'])

        # Adding model 'Annotation'
        db.create_table('receiver_annotation', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('attachment', self.gf('django.db.models.fields.related.ForeignKey')(related_name='annotations', to=orm['receiver.Attachment'])),
            ('date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('text', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='children', null=True, to=orm['receiver.Annotation'])),
        ))
        db.send_create_signal('receiver', ['Annotation'])

        # Adding model 'SubmissionHandlingType'
        db.create_table('receiver_submissionhandlingtype', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('app', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('method', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('receiver', ['SubmissionHandlingType'])

        # Adding model 'SubmissionHandlingOccurrence'
        db.create_table('receiver_submissionhandlingoccurrence', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('submission', self.gf('django.db.models.fields.related.ForeignKey')(related_name='ways_handled', to=orm['receiver.Submission'])),
            ('handled', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['receiver.SubmissionHandlingType'])),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal('receiver', ['SubmissionHandlingOccurrence'])


    def backwards(self, orm):
        
        # Deleting model 'Submission'
        db.delete_table('receiver_submission')

        # Deleting model 'Attachment'
        db.delete_table('receiver_attachment')

        # Deleting model 'Annotation'
        db.delete_table('receiver_annotation')

        # Deleting model 'SubmissionHandlingType'
        db.delete_table('receiver_submissionhandlingtype')

        # Deleting model 'SubmissionHandlingOccurrence'
        db.delete_table('receiver_submissionhandlingoccurrence')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'domain.domain': {
            'Meta': {'object_name': 'Domain'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        'domain.membership': {
            'Meta': {'object_name': 'Membership'},
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'member_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'member_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"})
        },
        'program.program': {
            'Meta': {'object_name': 'Program'},
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'program.programmembership': {
            'Meta': {'object_name': 'ProgramMembership'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'program': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['program.Program']"}),
            'program_member_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'program_member_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"})
        },
        'receiver.annotation': {
            'Meta': {'object_name': 'Annotation'},
            'attachment': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'annotations'", 'to': "orm['receiver.Attachment']"}),
            'date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['receiver.Annotation']"}),
            'text': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'receiver.attachment': {
            'Meta': {'ordering': "('-submission',)", 'object_name': 'Attachment'},
            'attachment_content_type': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'attachment_uri': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'checksum': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'filepath': ('django.db.models.fields.FilePathField', [], {'path': "'/home/rowena/workspace/core-hq/data/attachments'", 'max_length': '255', 'match': "'.*\\\\.attach$'"}),
            'filesize': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'attachments'", 'to': "orm['receiver.Submission']"})
        },
        'receiver.submission': {
            'Meta': {'ordering': "('-submit_time',)", 'object_name': 'Submission'},
            'authenticated_to': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
            'bytes_received': ('django.db.models.fields.IntegerField', [], {}),
            'checksum': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'content_type': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'raw_header': ('django.db.models.fields.TextField', [], {}),
            'raw_post': ('django.db.models.fields.FilePathField', [], {'max_length': '255', 'null': 'True', 'match': "'.*\\\\.postdata$'", 'path': "'/home/rowena/workspace/core-hq/data/submissions'"}),
            'submit_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'submit_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'transaction_uuid': ('django.db.models.fields.CharField', [], {'default': "'6a91b464-bc5c-11df-8c8b-5cff350164a3'", 'max_length': '36'})
        },
        'receiver.submissionhandlingoccurrence': {
            'Meta': {'object_name': 'SubmissionHandlingOccurrence'},
            'handled': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['receiver.SubmissionHandlingType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ways_handled'", 'to': "orm['receiver.Submission']"})
        },
        'receiver.submissionhandlingtype': {
            'Meta': {'object_name': 'SubmissionHandlingType'},
            'app': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['receiver']
