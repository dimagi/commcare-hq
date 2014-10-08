# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'SQLLocation'
        db.create_table(u'locations_sqllocation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('domain', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, null=True)),
            ('location_id', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('location_type', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('site_code', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('external_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('metadata', self.gf('json_field.fields.JSONField')(default={})),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('last_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('supply_point_id', self.gf('django.db.models.fields.CharField')(max_length=255, unique=True, null=True, db_index=True)),
            ('latitude', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=10)),
            ('longitude', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=10)),
        ))
        db.send_create_signal(u'locations', ['SQLLocation'])


    def backwards(self, orm):
        
        # Deleting model 'SQLLocation'
        db.delete_table(u'locations_sqllocation')


    models = {
        u'locations.sqllocation': {
            'Meta': {'object_name': 'SQLLocation'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            'location_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'location_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'longitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            'metadata': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'site_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'supply_point_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'db_index': 'True'})
        }
    }

    complete_apps = ['locations']
