# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'LocationType'
        db.create_table(u'locations_locationtype', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('code', self.gf('django.db.models.fields.SlugField')(max_length=50, null=True)),
            ('parent_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['locations.LocationType'], null=True)),
            ('administrative', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'locations', ['LocationType'])

        # Adding field 'SQLLocation.location_type'
        db.add_column(u'locations_sqllocation', 'location_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['locations.LocationType'], null=True), keep_default=False)


    def backwards(self, orm):

        # Deleting model 'LocationType'
        db.delete_table(u'locations_locationtype')

        # Deleting field 'SQLLocation.location_type'
        db.delete_column(u'locations_sqllocation', 'location_type_id')


    models = {
        u'locations.locationtype': {
            'Meta': {'object_name': 'LocationType'},
            'administrative': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'code': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'parent_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['locations.LocationType']", 'null': 'True'})
        },
        u'locations.sqllocation': {
            'Meta': {'unique_together': "(('domain', 'site_code'),)", 'object_name': 'SQLLocation'},
            '_products': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['products.SQLProduct']", 'null': 'True', 'symmetrical': 'False'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            'location_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['locations.LocationType']", 'null': 'True'}),
            'longitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            'metadata': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': u"orm['locations.SQLLocation']"}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'site_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'stocks_all_products': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'supply_point_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'db_index': 'True'}),
            'tmp_location_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        u'products.sqlproduct': {
            'Meta': {'object_name': 'SQLProduct'},
            'category': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'code': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'cost': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '5'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'product_data': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'product_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'db_index': 'True'}),
            'program_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'}),
            'units': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True'})
        }
    }

    complete_apps = ['locations']
