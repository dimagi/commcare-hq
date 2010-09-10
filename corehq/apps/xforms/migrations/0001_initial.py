# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'ElementDefModel'
        db.create_table('xforms_elementdefmodel', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('xpath', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('table_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('allowable_values_table', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('is_attribute', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_repeatable', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(related_name='children', null=True, to=orm['xforms.ElementDefModel'])),
            ('form', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xforms.FormDefModel'])),
        ))
        db.send_create_signal('xforms', ['ElementDefModel'])

        # Adding unique constraint on 'ElementDefModel', fields ['xpath', 'form']
        db.create_unique('xforms_elementdefmodel', ['xpath', 'form_id'])

        # Adding model 'FormDefModel'
        db.create_table('xforms_formdefmodel', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('uploaded_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['domain.Domain'], null=True, blank=True)),
            ('submit_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('submit_ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15, null=True)),
            ('bytes_received', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('xsd_file_location', self.gf('django.db.models.fields.FilePathField')(max_length=255, null=True, path='/home/rowena/workspace/core-hq/data/schemas')),
            ('xform_file_location', self.gf('django.db.models.fields.FilePathField')(max_length=255, null=True, path='/home/rowena/workspace/core-hq/data/schemas')),
            ('form_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('form_display_name', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('target_namespace', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('version', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('uiversion', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('date_created', self.gf('django.db.models.fields.DateField')(default=datetime.datetime(2010, 9, 9, 17, 53, 41, 256938))),
            ('element', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['xforms.ElementDefModel'], unique=True, null=True)),
        ))
        db.send_create_signal('xforms', ['FormDefModel'])

        # Adding unique constraint on 'FormDefModel', fields ['domain', 'target_namespace', 'version']
        db.create_unique('xforms_formdefmodel', ['domain_id', 'target_namespace', 'version'])

        # Adding model 'Metadata'
        db.create_table('xforms_metadata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('formname', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('formversion', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('deviceid', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('timestart', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('timeend', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('chw_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('uid', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
            ('attachment', self.gf('django.db.models.fields.related.ForeignKey')(related_name='form_metadata', to=orm['receiver.Attachment'])),
            ('raw_data', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('formdefmodel', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xforms.FormDefModel'], null=True)),
            ('version', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('uiversion', self.gf('django.db.models.fields.IntegerField')(null=True)),
        ))
        db.send_create_signal('xforms', ['Metadata'])

        # Adding model 'FormDataPointer'
        db.create_table('xforms_formdatapointer', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('form', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xforms.FormDefModel'])),
            ('column_name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=20)),
        ))
        db.send_create_signal('xforms', ['FormDataPointer'])

        # Adding unique constraint on 'FormDataPointer', fields ['form', 'column_name']
        db.create_unique('xforms_formdatapointer', ['form_id', 'column_name'])

        # Adding model 'FormDataColumn'
        db.create_table('xforms_formdatacolumn', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=20)),
        ))
        db.send_create_signal('xforms', ['FormDataColumn'])

        # Adding M2M table for field fields on 'FormDataColumn'
        db.create_table('xforms_formdatacolumn_fields', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('formdatacolumn', models.ForeignKey(orm['xforms.formdatacolumn'], null=False)),
            ('formdatapointer', models.ForeignKey(orm['xforms.formdatapointer'], null=False))
        ))
        db.create_unique('xforms_formdatacolumn_fields', ['formdatacolumn_id', 'formdatapointer_id'])

        # Adding model 'FormDataGroup'
        db.create_table('xforms_formdatagroup', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['domain.Domain'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('display_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('view_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=64)),
        ))
        db.send_create_signal('xforms', ['FormDataGroup'])

        # Adding M2M table for field forms on 'FormDataGroup'
        db.create_table('xforms_formdatagroup_forms', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('formdatagroup', models.ForeignKey(orm['xforms.formdatagroup'], null=False)),
            ('formdefmodel', models.ForeignKey(orm['xforms.formdefmodel'], null=False))
        ))
        db.create_unique('xforms_formdatagroup_forms', ['formdatagroup_id', 'formdefmodel_id'])

        # Adding M2M table for field columns on 'FormDataGroup'
        db.create_table('xforms_formdatagroup_columns', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('formdatagroup', models.ForeignKey(orm['xforms.formdatagroup'], null=False)),
            ('formdatacolumn', models.ForeignKey(orm['xforms.formdatacolumn'], null=False))
        ))
        db.create_unique('xforms_formdatagroup_columns', ['formdatagroup_id', 'formdatacolumn_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'FormDataPointer', fields ['form', 'column_name']
        db.delete_unique('xforms_formdatapointer', ['form_id', 'column_name'])

        # Removing unique constraint on 'FormDefModel', fields ['domain', 'target_namespace', 'version']
        db.delete_unique('xforms_formdefmodel', ['domain_id', 'target_namespace', 'version'])

        # Removing unique constraint on 'ElementDefModel', fields ['xpath', 'form']
        db.delete_unique('xforms_elementdefmodel', ['xpath', 'form_id'])

        # Deleting model 'ElementDefModel'
        db.delete_table('xforms_elementdefmodel')

        # Deleting model 'FormDefModel'
        db.delete_table('xforms_formdefmodel')

        # Deleting model 'Metadata'
        db.delete_table('xforms_metadata')

        # Deleting model 'FormDataPointer'
        db.delete_table('xforms_formdatapointer')

        # Deleting model 'FormDataColumn'
        db.delete_table('xforms_formdatacolumn')

        # Removing M2M table for field fields on 'FormDataColumn'
        db.delete_table('xforms_formdatacolumn_fields')

        # Deleting model 'FormDataGroup'
        db.delete_table('xforms_formdatagroup')

        # Removing M2M table for field forms on 'FormDataGroup'
        db.delete_table('xforms_formdatagroup_forms')

        # Removing M2M table for field columns on 'FormDataGroup'
        db.delete_table('xforms_formdatagroup_columns')


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
            'transaction_uuid': ('django.db.models.fields.CharField', [], {'default': "'b5848ec4-bc5c-11df-bd48-5cff350164a3'", 'max_length': '36'})
        },
        'xforms.elementdefmodel': {
            'Meta': {'unique_together': "(('xpath', 'form'),)", 'object_name': 'ElementDefModel'},
            'allowable_values_table': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'form': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xforms.FormDefModel']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_attribute': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_repeatable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'children'", 'null': 'True', 'to': "orm['xforms.ElementDefModel']"}),
            'table_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'xpath': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'xforms.formdatacolumn': {
            'Meta': {'object_name': 'FormDataColumn'},
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'fields': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'columns'", 'symmetrical': 'False', 'to': "orm['xforms.FormDataPointer']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'xforms.formdatagroup': {
            'Meta': {'object_name': 'FormDataGroup'},
            'columns': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'groups'", 'symmetrical': 'False', 'to': "orm['xforms.FormDataColumn']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']"}),
            'forms': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['xforms.FormDefModel']", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'view_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        'xforms.formdatapointer': {
            'Meta': {'unique_together': "(('form', 'column_name'),)", 'object_name': 'FormDataPointer'},
            'column_name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'form': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xforms.FormDefModel']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'xforms.formdefmodel': {
            'Meta': {'unique_together': "(('domain', 'target_namespace', 'version'),)", 'object_name': 'FormDefModel'},
            'bytes_received': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'date_created': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2010, 9, 9, 17, 53, 41, 272798)'}),
            'domain': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['domain.Domain']", 'null': 'True', 'blank': 'True'}),
            'element': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['xforms.ElementDefModel']", 'unique': 'True', 'null': 'True'}),
            'form_display_name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'form_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submit_ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'null': 'True'}),
            'submit_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'target_namespace': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'uiversion': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'uploaded_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
            'version': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'xform_file_location': ('django.db.models.fields.FilePathField', [], {'max_length': '255', 'null': 'True', 'path': "'/home/rowena/workspace/core-hq/data/schemas'"}),
            'xsd_file_location': ('django.db.models.fields.FilePathField', [], {'max_length': '255', 'null': 'True', 'path': "'/home/rowena/workspace/core-hq/data/schemas'"})
        },
        'xforms.metadata': {
            'Meta': {'object_name': 'Metadata'},
            'attachment': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'form_metadata'", 'to': "orm['receiver.Attachment']"}),
            'chw_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'deviceid': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'formdefmodel': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xforms.FormDefModel']", 'null': 'True'}),
            'formname': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'formversion': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'raw_data': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'timeend': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'timestart': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'uid': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'uiversion': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'version': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        }
    }

    complete_apps = ['xforms']
