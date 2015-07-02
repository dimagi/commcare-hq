# encoding: utf-8
from south.db import db
from south.v2 import SchemaMigration

class Migration(SchemaMigration):

    def forwards(self, orm):
        db.execute("DROP INDEX IF EXISTS phone_ownershipcleanliness_domain_like")
        db.execute("DROP INDEX IF EXISTS phone_ownershipcleanliness_owner_id_like")
        db.execute("DROP INDEX IF EXISTS phone_ownershipcleanlinessflag_domain_like")
        db.execute("DROP INDEX IF EXISTS phone_ownershipcleanlinessflag_owner_id_like")

    def backwards(self, orm):
        # don't add it back
        pass

    models = {
        u'phone.ownershipcleanlinessflag': {
            'Meta': {'unique_together': "[('domain', 'owner_id')]", 'object_name': 'OwnershipCleanlinessFlag'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'hint': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_clean': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_checked': ('django.db.models.fields.DateTimeField', [], {}),
            'owner_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        }
    }

    complete_apps = ['phone']
