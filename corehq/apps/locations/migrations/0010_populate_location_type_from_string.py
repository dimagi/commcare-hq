# encoding: utf-8
from south.v2 import DataMigration
from corehq.apps.domain.models import Domain


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


def _couch_parent_loc(parent_code, couch_loc_types, domain):
    for loc_type in couch_loc_types:
        if loc_type.get('code') == parent_code or loc_type['name'] == parent_code:
            return loc_type
    raise ValueError("Parent loc type {} not found on {}"
                     .format(parent_code, domain))


class Migration(DataMigration):

    def make_loc_types(self, couch_loc_types, domain):

        def get_or_create(couch_loc_type):
            parents = couch_loc_type['allowed_parents']
            if len(parents) != 1:
                raise ValueError("Improperly configured location types on {}"
                                 .format(domain))
            elif parents[0] == '':
                parent_type = None
            else:
                parent_type = get_or_create(
                    _couch_parent_loc(parents[0], couch_loc_types, domain)
                )

            return self.orm.LocationType.objects.get_or_create(
                domain=domain,
                code=couch_loc_type.get('code', couch_loc_type['name']),
                defaults={
                    'name': couch_loc_type['name'],
                    'parent_type': parent_type,
                    'administrative': couch_loc_type['administrative'] or False,
                    'shares_cases': couch_loc_type.get('shares_cases') or False,
                    'view_descendants': couch_loc_type.get('view_descendants') or False,
                }
            )[0]

        loc_types = {}
        for lt in couch_loc_types:
            loc_type = get_or_create(lt)
            if 'code' in lt:
                loc_types[lt['code']] = loc_type
            loc_types[lt['name']] = loc_type
        return loc_types

    def link_locs_to_types(self, loc_types, domain):
        for loc in (
            self.orm.SQLLocation.objects.filter(domain=domain).iterator()
        ):
            if loc.tmp_location_type not in loc_types:
                raise KeyError('loc_type {} not found on domain "{}"'
                               .format(loc.tmp_location_type, domain))
            loc.location_type = loc_types[loc.tmp_location_type]
            loc.save()

    def forwards(self, orm):
        """
        Look up the old LocationType docs, make SQL LocationTypes based on that
        and then link to locations on the domain.
        """
        self.orm = orm
        for domain_obj in Domain.get_all():
            domain_json = domain_obj.to_json()
            loc_types = domain_json.get('obsolete_location_types')
            if loc_types is None:
                loc_types = domain_json.get('location_types')

            if loc_types:
                sql_loc_types = self.make_loc_types(loc_types, domain_obj.name)
                self.link_locs_to_types(sql_loc_types, domain_obj.name)

    def backwards(self, orm):
        """
        Populate the tmp_location_type field based on the location_type object
        """
        for loc in orm.SQLLocation.objects.iterator():
            loc_type_str = loc.location_type.name if loc.location_type else ''
            if loc_type_str and loc_type_str != loc.tmp_location_type:
                loc.tmp_location_type = loc_type_str
                loc.save()

    models = {
        u'locations.locationtype': {
            'Meta': {'object_name': 'LocationType'},
            'administrative': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'code': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'parent_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['locations.LocationType']", 'null': 'True'}),
            'shares_cases': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'view_descendants': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
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
