from django.test import TestCase
from corehq.apps.facilities.dbaccessors import \
    get_facility_registries_in_domain
from corehq.apps.facilities.models import FacilityRegistry


class DBAccessorsTest(TestCase):
    def test_get_facility_registries_in_domain(self):
        objects = []
        domain = 'facility-registry-dbaccessors'
        try:
            self.assertEqual(get_facility_registries_in_domain(domain), [])
            o = FacilityRegistry(domain=domain)
            o.save()
            objects.append(o)
            self.assertItemsEqual(
                [o.to_json() for o in get_facility_registries_in_domain(domain)],
                [o.to_json() for o in objects],
            )
            o = FacilityRegistry(domain=domain)
            o.save()
            objects.append(o)
            self.assertItemsEqual(
                [o.to_json() for o in get_facility_registries_in_domain(domain)],
                [o.to_json() for o in objects],
            )
        finally:
            FacilityRegistry.get_db().bulk_delete(objects)
