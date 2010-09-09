# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Domain'
        db.create_table('domain_domain', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=64)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('domain', ['Domain'])

        # Adding model 'Membership'
        db.create_table('domain_membership', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['domain.Domain'])),
            ('member_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('member_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('domain', ['Membership'])

        # Adding model 'RegistrationRequest'
        db.create_table('domain_registration_request', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('tos_confirmed', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('request_time', self.gf('django.db.models.fields.DateTimeField')()),
            ('request_ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('activation_guid', self.gf('django.db.models.fields.CharField')(unique=True, max_length=32)),
            ('confirm_time', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('confirm_ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15, null=True, blank=True)),
            ('domain', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['domain.Domain'], unique=True)),
            ('new_user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='new_user', to=orm['auth.User'])),
            ('requesting_user', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='requesting_user', null=True, to=orm['auth.User'])),
        ))
        db.send_create_signal('domain', ['RegistrationRequest'])

        # Adding model 'Settings'
        db.create_table('domain_settings', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['domain.Domain'], unique=True)),
            ('max_users', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('domain', ['Settings'])


    def backwards(self, orm):
        
        # Deleting model 'Domain'
        db.delete_table('domain_domain')

        # Deleting model 'Membership'
        db.delete_table('domain_membership')

        # Deleting model 'RegistrationRequest'
        db.delete_table('domain_registration_request')

        # Deleting model 'Settings'
        db.delete_table('domain_settings')


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
        'domain.registrationrequest': {
            'Meta': {'object_name': 'RegistrationRequest', 'db_table': "'domain_registration_request'"},
            'activation_guid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'}),
            'confirm_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'null': 'True', 'blank': 'True'}),
            'confirm_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['domain.Domain']", 'unique': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'new_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'new_user'", 'to': "orm['auth.User']"}),
            'request_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'request_time': ('django.db.models.fields.DateTimeField', [], {}),
            'requesting_user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'requesting_user'", 'null': 'True', 'to': "orm['auth.User']"}),
            'tos_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'domain.settings': {
            'Meta': {'object_name': 'Settings'},
            'domain': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['domain.Domain']", 'unique': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_users': ('django.db.models.fields.PositiveIntegerField', [], {})
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
        }
    }

    complete_apps = ['domain']
