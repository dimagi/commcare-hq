# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'AuditEvent'
        db.create_table('auditor_auditevent', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('event_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2010, 9, 9, 20, 43, 31, 885134))),
            ('event_class', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=160)),
        ))
        db.send_create_signal('auditor', ['AuditEvent'])

        # Adding model 'ModelActionAudit'
        db.create_table('auditor_modelactionaudit', (
            ('auditevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auditor.AuditEvent'], unique=True, primary_key=True)),
            ('object_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True, blank=True)),
            ('object_uuid', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=32, null=True, blank=True)),
        ))
        db.send_create_signal('auditor', ['ModelActionAudit'])

        # Adding model 'NavigationEventAudit'
        db.create_table('auditor_navigationeventaudit', (
            ('auditevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auditor.AuditEvent'], unique=True, primary_key=True)),
            ('request_path', self.gf('django.db.models.fields.TextField')()),
            ('ip_address', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('view', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('headers', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('session_key', self.gf('django.db.models.fields.CharField')(max_length=40)),
        ))
        db.send_create_signal('auditor', ['NavigationEventAudit'])

        # Adding model 'AccessAudit'
        db.create_table('auditor_accessaudit', (
            ('auditevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auditor.AuditEvent'], unique=True, primary_key=True)),
            ('access_type', self.gf('django.db.models.fields.CharField')(max_length=12)),
            ('ip_address', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('session_key', self.gf('django.db.models.fields.CharField')(max_length=40)),
        ))
        db.send_create_signal('auditor', ['AccessAudit'])

        # Adding model 'FieldAccess'
        db.create_table('auditor_fieldaccess', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('object_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True, blank=True)),
            ('field', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
        ))
        db.send_create_signal('auditor', ['FieldAccess'])

        # Adding unique constraint on 'FieldAccess', fields ['object_type', 'field']
        db.create_unique('auditor_fieldaccess', ['object_type_id', 'field'])

        # Adding model 'ModelAuditEvent'
        db.create_table('auditor_modelauditevent', (
            ('id', self.gf('django.db.models.fields.CharField')(default='e8868b9cbc5211dfbbac5cff350164a3', unique=True, max_length=32, primary_key=True)),
            ('object_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True, blank=True)),
            ('object_uuid', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=32, null=True, blank=True)),
            ('property_data', self.gf('django.db.models.fields.TextField')()),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('accessed', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2010, 9, 9, 20, 43, 31, 872164))),
        ))
        db.send_create_signal('auditor', ['ModelAuditEvent'])

        # Adding M2M table for field properties on 'ModelAuditEvent'
        db.create_table('auditor_modelauditevent_properties', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('modelauditevent', models.ForeignKey(orm['auditor.modelauditevent'], null=False)),
            ('fieldaccess', models.ForeignKey(orm['auditor.fieldaccess'], null=False))
        ))
        db.create_unique('auditor_modelauditevent_properties', ['modelauditevent_id', 'fieldaccess_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'FieldAccess', fields ['object_type', 'field']
        db.delete_unique('auditor_fieldaccess', ['object_type_id', 'field'])

        # Deleting model 'AuditEvent'
        db.delete_table('auditor_auditevent')

        # Deleting model 'ModelActionAudit'
        db.delete_table('auditor_modelactionaudit')

        # Deleting model 'NavigationEventAudit'
        db.delete_table('auditor_navigationeventaudit')

        # Deleting model 'AccessAudit'
        db.delete_table('auditor_accessaudit')

        # Deleting model 'FieldAccess'
        db.delete_table('auditor_fieldaccess')

        # Deleting model 'ModelAuditEvent'
        db.delete_table('auditor_modelauditevent')

        # Removing M2M table for field properties on 'ModelAuditEvent'
        db.delete_table('auditor_modelauditevent_properties')


    models = {
        'auditor.accessaudit': {
            'Meta': {'object_name': 'AccessAudit', '_ormbases': ['auditor.AuditEvent']},
            'access_type': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
            'auditevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auditor.AuditEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'})
        },
        'auditor.auditevent': {
            'Meta': {'object_name': 'AuditEvent'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '160'}),
            'event_class': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'event_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2010, 9, 9, 20, 43, 31, 897960)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'auditor.fieldaccess': {
            'Meta': {'unique_together': "(('object_type', 'field'),)", 'object_name': 'FieldAccess'},
            'field': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'})
        },
        'auditor.modelactionaudit': {
            'Meta': {'object_name': 'ModelActionAudit', '_ormbases': ['auditor.AuditEvent']},
            'auditevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auditor.AuditEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'object_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'object_uuid': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '32', 'null': 'True', 'blank': 'True'})
        },
        'auditor.modelauditevent': {
            'Meta': {'object_name': 'ModelAuditEvent'},
            'accessed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2010, 9, 9, 20, 43, 31, 872164)'}),
            'id': ('django.db.models.fields.CharField', [], {'default': "'e8888712bc5211dfbbac5cff350164a3'", 'unique': 'True', 'max_length': '32', 'primary_key': 'True'}),
            'object_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'object_uuid': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'properties': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['auditor.FieldAccess']", 'null': 'True', 'blank': 'True'}),
            'property_data': ('django.db.models.fields.TextField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'auditor.navigationeventaudit': {
            'Meta': {'object_name': 'NavigationEventAudit', '_ormbases': ['auditor.AuditEvent']},
            'auditevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auditor.AuditEvent']", 'unique': 'True', 'primary_key': 'True'}),
            'headers': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'ip_address': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'request_path': ('django.db.models.fields.TextField', [], {}),
            'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'view': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
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
        }
    }

    complete_apps = ['auditor']
