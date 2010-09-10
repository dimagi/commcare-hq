# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Jarjad'
        db.create_table('releasemanager_jarjad', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('uploaded_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='core_uploaded', to=orm['auth.User'])),
            ('is_release', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, unique=True, null=True, blank=True)),
            ('build_number', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True)),
            ('revision_number', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=20, null=True, blank=True)),
            ('jad_file', self.gf('django.db.models.fields.FilePathField')(path='data/release/jarjad', max_length=255, recursive=True, match='.*\\.jad$')),
            ('jar_file', self.gf('django.db.models.fields.FilePathField')(path='data/release/jarjad', max_length=255, recursive=True, match='.*\\.jar$')),
        ))
        db.send_create_signal('releasemanager', ['Jarjad'])

        # Adding unique constraint on 'Jarjad', fields ['build_number', 'revision_number', 'version']
        db.create_unique('releasemanager_jarjad', ['build_number', 'revision_number', 'version'])

        # Adding model 'ResourceSet'
        db.create_table('releasemanager_resourceset', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['domain.Domain'])),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=512)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('is_release', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('releasemanager', ['ResourceSet'])

        # Adding model 'Build'
        db.create_table('releasemanager_build', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('is_release', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('jarjad', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['releasemanager.Jarjad'])),
            ('resource_set', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['releasemanager.ResourceSet'])),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255, unique=True, null=True, blank=True)),
            ('jar_file', self.gf('django.db.models.fields.FilePathField')(path='data/release/builds', max_length=255, recursive=True, match='.*\\.jar$')),
            ('jad_file', self.gf('django.db.models.fields.FilePathField')(path='data/release/builds', max_length=255, recursive=True, match='.*\\.jad$')),
            ('zip_file', self.gf('django.db.models.fields.FilePathField')(path='data/release/builds', max_length=255, recursive=True, match='.*\\.zip$')),
        ))
        db.send_create_signal('releasemanager', ['Build'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'Jarjad', fields ['build_number', 'revision_number', 'version']
        db.delete_unique('releasemanager_jarjad', ['build_number', 'revision_number', 'version'])

        # Deleting model 'Jarjad'
        db.delete_table('releasemanager_jarjad')

        # Deleting model 'ResourceSet'
        db.delete_table('releasemanager_resourceset')

        # Deleting model 'Build'
        db.delete_table('releasemanager_build')


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
        'releasemanager.build': {
            'Meta': {'object_name': 'Build'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_release': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'jad_file': ('django.db.models.fields.FilePathField', [], {'path': "'data/release/builds'", 'max_length': '255', 'recursive': 'True', 'match': "'.*\\\\.jad$'"}),
            'jar_file': ('django.db.models.fields.FilePathField', [], {'path': "'data/release/builds'", 'max_length': '255', 'recursive': 'True', 'match': "'.*\\\\.jar$'"}),
            'jarjad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['releasemanager.Jarjad']"}),
            'resource_set': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['releasemanager.ResourceSet']"}),
            'zip_file': ('django.db.models.fields.FilePathField', [], {'path': "'data/release/builds'", 'max_length': '255', 'recursive': 'True', 'match': "'.*\\\\.zip$'"})
        },
        'releasemanager.jarjad': {
            'Meta': {'unique_together': "(('build_number', 'revision_number', 'version'),)", 'object_name': 'Jarjad'},
            'build_number': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_release': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'jad_file': ('django.db.models.fields.FilePathField', [], {'path': "'data/release/jarjad'", 'max_length': '255', 'recursive': 'True', 'match': "'.*\\\\.jad$'"}),
            'jar_file': ('django.db.models.fields.FilePathField', [], {'path': "'data/release/jarjad'", 'max_length': '255', 'recursive': 'True', 'match': "'.*\\\\.jar$'"}),
            'revision_number': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'core_uploaded'", 'to': "orm['auth.User']"}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
        },
        'releasemanager.resourceset': {
            'Meta': {'object_name': 'ResourceSet'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_release': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '512'})
        }
    }

    complete_apps = ['releasemanager']
