# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Phone'
        db.create_table('phone_phone', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device_id', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(related_name='phones', to=orm['domain.Domain'])),
        ))
        db.send_create_signal('phone', ['Phone'])

        # Adding model 'PhoneUserInfo'
        db.create_table('phone_phoneuserinfo', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='phone_registrations', null=True, to=orm['auth.User'])),
            ('phone', self.gf('django.db.models.fields.related.ForeignKey')(related_name='users', to=orm['phone.Phone'])),
            ('attachment', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['receiver.Attachment'], unique=True, null=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
            ('uuid', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
            ('registered_on', self.gf('django.db.models.fields.DateField')(default=datetime.datetime(2010, 9, 9, 17, 53, 23, 170))),
            ('additional_data', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('phone', ['PhoneUserInfo'])

        # Adding unique constraint on 'PhoneUserInfo', fields ['phone', 'username']
        db.create_unique('phone_phoneuserinfo', ['phone_id', 'username'])

        # Adding model 'PhoneBackup'
        db.create_table('phone_phonebackup', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('attachment', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['receiver.Attachment'])),
            ('phone', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['phone.Phone'])),
        ))
        db.send_create_signal('phone', ['PhoneBackup'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'PhoneUserInfo', fields ['phone', 'username']
        db.delete_unique('phone_phoneuserinfo', ['phone_id', 'username'])

        # Deleting model 'Phone'
        db.delete_table('phone_phone')

        # Deleting model 'PhoneUserInfo'
        db.delete_table('phone_phoneuserinfo')

        # Deleting model 'PhoneBackup'
        db.delete_table('phone_phonebackup')


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
        'phone.phone': {
            'Meta': {'object_name': 'Phone'},
            'device_id': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'phones'", 'to': "orm['domain.Domain']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'phone.phonebackup': {
            'Meta': {'object_name': 'PhoneBackup'},
            'attachment': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['receiver.Attachment']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'phone': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['phone.Phone']"})
        },
        'phone.phoneuserinfo': {
            'Meta': {'unique_together': "(('phone', 'username'),)", 'object_name': 'PhoneUserInfo'},
            'additional_data': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'attachment': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['receiver.Attachment']", 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'phone': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'users'", 'to': "orm['phone.Phone']"}),
            'registered_on': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2010, 9, 9, 17, 53, 23, 10975)'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'phone_registrations'", 'null': 'True', 'to': "orm['auth.User']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'uuid': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'})
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
            'transaction_uuid': ('django.db.models.fields.CharField', [], {'default': "'aaa0c554-bc5c-11df-a890-5cff350164a3'", 'max_length': '36'})
        }
    }

    complete_apps = ['phone']
