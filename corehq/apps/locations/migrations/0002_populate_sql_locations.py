# encoding: utf-8
from south.v2 import DataMigration
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.commtrack.models import SupplyPointCase
from dimagi.utils.couch.database import iter_docs
import corehq.apps.locations.models as location_models
from dimagi.utils.couch import sync_docs


class Migration(DataMigration):

    def forwards(self, orm):
        # hack: manually force sync Location design docs before
        # we try to load from them
        sync_docs.sync(location_models, verbosity=2)

        properties_to_sync = [
            ('location_id', '_id'),
            'domain',
            'name',
            'location_type',
            'site_code',
            'external_id',
            'latitude',
            'longitude',
            'is_archived',
        ]

        location_ids = set([r['id'] for r in Location.get_db().view(
            'locations/by_name',
            reduce=False,
        ).all()])

        for location in iter_docs(Location.get_db(), location_ids):
            try:
                sql_location = orm.SQLLocation.objects.get(location_id=location['_id'])
            except orm.SQLLocation.DoesNotExist:
                # this populates bogus mptt data because otherwise
                # null constraints will blow up but do not worry, we
                # rebuild this at the end
                sql_location = orm.SQLLocation.objects.create(
                    location_id=location['_id'],
                    lft=0,
                    rght=0,
                    tree_id=0,
                    level=0
                )

            for prop in properties_to_sync:
                if isinstance(prop, tuple):
                    sql_prop, couch_prop = prop
                else:
                    sql_prop = couch_prop = prop

                if couch_prop in location:
                    setattr(sql_location, sql_prop, location[couch_prop])

            # sync supply point id
            sp = SupplyPointCase.view(
                'commtrack/supply_point_by_loc',
                key=[location['domain'], location['_id']],
                include_docs=True,
                classes={'CommCareCase': SupplyPointCase},
            ).one()
            if sp:
                sql_location.supply_point_id = sp._id

            # sync parent connection
            parent_id = location.get('parent_id', None)
            if parent_id:
                sql_location.parent = orm.SQLLocation.objects.get(location_id=parent_id)

            sql_location.save()

        # this is the important bit that rebuilds mptt tree structures
        SQLLocation.objects.rebuild()

    def backwards(self, orm):
        orm.SQLLocation.objects.all().delete()

    models = {
        u'locations.sqllocation': {
            'Meta': {'object_name': 'SQLLocation'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_archived': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location_id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'location_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'longitude': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '10'}),
            'metadata': ('json_field.fields.JSONField', [], {'default': '{}'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': u"orm['locations.SQLLocation']"}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'site_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'supply_point_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'db_index': 'True'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['locations']
