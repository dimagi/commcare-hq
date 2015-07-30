# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    depends_on = (
        ('ilsgateway', '0007_auto__del_ilsmigrationcheckpoint__add_logisticsmigrationcheckpoint'),
    )

    def forwards(self, orm):
        db.rename_table(u'ilsgateway_logisticsmigrationcheckpoint', u'logistics_migrationcheckpoint')

        if not db.dry_run:
            orm['contenttypes.contenttype'].objects.filter(
                app_label='ilsgateway',
                model='migrationcheckpoint'
            ).update(app_label='logistics')

    def backwards(self, orm):
        pass


    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'logistics.migrationcheckpoint': {
            'Meta': {'object_name': 'LogisticsMigrationCheckpoint'},
            'api': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'limit': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'offset': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        }
    }

    complete_apps = ['logistics']
