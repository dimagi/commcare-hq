# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'BaseGraph'
        db.create_table('graphing_basegraph', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('shortname', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=128)),
        ))
        db.send_create_signal('graphing', ['BaseGraph'])

        # Adding model 'RawGraph'
        db.create_table('graphing_rawgraph', (
            ('basegraph_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['graphing.BaseGraph'], unique=True, primary_key=True)),
            ('table_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('data_source', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('db_query', self.gf('django.db.models.fields.TextField')()),
            ('y_axis_label', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('x_axis_label', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('x_type', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('series_labels', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('display_type', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('time_bound', self.gf('django.db.models.fields.NullBooleanField')(default=False, null=True, blank=True)),
            ('default_interval', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('interval_ranges', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('additional_options', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('width', self.gf('django.db.models.fields.IntegerField')(default=950)),
            ('height', self.gf('django.db.models.fields.IntegerField')(default=300)),
        ))
        db.send_create_signal('graphing', ['RawGraph'])

        # Adding model 'GraphGroup'
        db.create_table('graphing_graphgroup', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('parent_group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['graphing.GraphGroup'], null=True, blank=True)),
        ))
        db.send_create_signal('graphing', ['GraphGroup'])

        # Adding M2M table for field graphs on 'GraphGroup'
        db.create_table('graphing_graphgroup_graphs', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('graphgroup', models.ForeignKey(orm['graphing.graphgroup'], null=False)),
            ('basegraph', models.ForeignKey(orm['graphing.basegraph'], null=False))
        ))
        db.create_unique('graphing_graphgroup_graphs', ['graphgroup_id', 'basegraph_id'])

        # Adding model 'GraphPref'
        db.create_table('graphing_graphpref', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
        ))
        db.send_create_signal('graphing', ['GraphPref'])

        # Adding M2M table for field root_graphs on 'GraphPref'
        db.create_table('graphing_graphpref_root_graphs', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('graphpref', models.ForeignKey(orm['graphing.graphpref'], null=False)),
            ('graphgroup', models.ForeignKey(orm['graphing.graphgroup'], null=False))
        ))
        db.create_unique('graphing_graphpref_root_graphs', ['graphpref_id', 'graphgroup_id'])


    def backwards(self, orm):
        
        # Deleting model 'BaseGraph'
        db.delete_table('graphing_basegraph')

        # Deleting model 'RawGraph'
        db.delete_table('graphing_rawgraph')

        # Deleting model 'GraphGroup'
        db.delete_table('graphing_graphgroup')

        # Removing M2M table for field graphs on 'GraphGroup'
        db.delete_table('graphing_graphgroup_graphs')

        # Deleting model 'GraphPref'
        db.delete_table('graphing_graphpref')

        # Removing M2M table for field root_graphs on 'GraphPref'
        db.delete_table('graphing_graphpref_root_graphs')


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
        'graphing.basegraph': {
            'Meta': {'ordering': "('-id',)", 'object_name': 'BaseGraph'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'shortname': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'graphing.graphgroup': {
            'Meta': {'object_name': 'GraphGroup'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'graphs': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['graphing.BaseGraph']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'parent_group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['graphing.GraphGroup']", 'null': 'True', 'blank': 'True'})
        },
        'graphing.graphpref': {
            'Meta': {'object_name': 'GraphPref'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'root_graphs': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['graphing.GraphGroup']", 'symmetrical': 'False'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'graphing.rawgraph': {
            'Meta': {'ordering': "('-id',)", 'object_name': 'RawGraph', '_ormbases': ['graphing.BaseGraph']},
            'additional_options': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'basegraph_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['graphing.BaseGraph']", 'unique': 'True', 'primary_key': 'True'}),
            'data_source': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'db_query': ('django.db.models.fields.TextField', [], {}),
            'default_interval': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'display_type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'height': ('django.db.models.fields.IntegerField', [], {'default': '300'}),
            'interval_ranges': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'series_labels': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'table_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time_bound': ('django.db.models.fields.NullBooleanField', [], {'default': 'False', 'null': 'True', 'blank': 'True'}),
            'width': ('django.db.models.fields.IntegerField', [], {'default': '950'}),
            'x_axis_label': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'x_type': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'y_axis_label': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'})
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

    complete_apps = ['graphing']
