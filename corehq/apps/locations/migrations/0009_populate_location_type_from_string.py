# encoding: utf-8
from south.v2 import DataMigration
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch.database import get_db, iter_docs
from dimagi.utils.chunked import chunked


EXCLUDE_DOMAINS = (
    "drewpsi",
    "psi",
    "psi-ors",
    "psi-test",
    "psi-test2",
    "psi-test3",
    "psi-unicef",
    "psi-unicef-wb",
)


class Migration(DataMigration):

    @memoized
    def domain_loc_types(self, domain):
        domain = get_db().view("domain/domains", key=domain, reduce=False,
                               include_docs=True).one()
        return {
            # It looks like code is what I should use, not name
            loc_type['code']: loc_type
            for loc_type in domain.get('location_types', [])
        }

    def iter_relevant_locations(self):
        return (self.orm.SQLLocation.objects.exclude(domain__in=EXCLUDE_DOMAINS)
                                       .iterator())

    @memoized
    def get_loc_type(self, domain, code):
        """
        Get or create relevant SQL location type
        """
        try:
            loc_type = self.orm.LocationType.objects.get(domain=domain, code=code)
        except self.orm.LocationType.DoesNotExist:
            loc_types = self.domain_loc_types(domain)
            if not loc_types:
                couch_loc_type = {
                    'allowed_parents': [''],
                    'name': 'state',
                    'code': 'state',
                    'administrative': False,
                }
            elif code in loc_types:
                couch_loc_type = loc_types[code]
            else:
                couch_loc_type = loc_types.values()[0]

            parents = couch_loc_type['allowed_parents']
            if parents and parents[0]:
                # I sure hope there are no cycles...
                parent_type = self.get_loc_type(domain, parents[0])
            else:
                parent_type = None

            loc_type = self.orm.LocationType(
                domain=domain,
                name=couch_loc_type['name'],
                code=couch_loc_type['code'],
                parent_type=parent_type,
                administrative=couch_loc_type['administrative'] or False,
            )
            loc_type.save()

        return loc_type

    def forwards(self, orm):
        """
        Get all SQLLocations, get or create the appropriate location_type,
        based on the old location_type string, save a foreign key to it.
        """
        self.orm = orm
        for loc in self.iter_relevant_locations():
            loc_type = self.get_loc_type(loc.domain, loc.tmp_location_type)
            loc.location_type = loc_type
            loc.save()

        # Clean the 'location_types' field off all domains.
        # Note that this is not reversible
        db = get_db()
        all_domain_ids = [d['id'] for d in db.view("domain/not_snapshots",
                                                   include_docs=False).all()]
        for domain_docs in chunked(iter_docs(db, all_domain_ids), 100):
            for domain_doc in domain_docs:
                if 'location_types' in domain_doc:
                    del domain_doc['location_types']
            db.bulk_save(domain_docs)

    def backwards(self, orm):
        """
        Get all SQLLocations, populate the tmp_location_type field with the
        location_type.code
        """
        self.orm = orm
        for loc in self.iter_relevant_locations():
            if loc.location_type:
                loc.tmp_location_type = loc.location_type.code
                loc.save()

    models = {
        u'locations.locationtype': {
            'Meta': {'object_name': 'LocationType'},
            'administrative': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'code': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
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
