from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.commtrack.const import DAYS_IN_MONTH
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import Location
from corehq.apps.locations.bulk import LocationImporter
from mock import patch
from corehq.apps.consumption.shortcuts import get_default_consumption
from corehq.apps.products.models import Product


def import_location(domain, loc_type, data):
    excel_importer = type("FakeImporter", (), {"worksheets": []})
    importer = LocationImporter(domain, excel_importer)
    return importer.import_location(loc_type, data)


class LocationImportTest(CommTrackTest):
    def setUp(self):
        super(LocationImportTest, self).setUp()
        # set up a couple locations that make tests a little more DRY
        self.test_state = make_loc('sillyparentstate', type='state')
        self.test_village = make_loc('sillyparentvillage', type='village')

    def names_of_locs(self):
        return [loc.name for loc in Location.by_domain(self.domain.name)]

    def test_import_new_top_level_location(self):
        data = {
            'name': 'importedloc'
        }

        import_location(self.domain.name, 'state', data)

        self.assertTrue(data['name'] in self.names_of_locs())

    def test_import_with_existing_parent_by_site_code(self):
        data = {
            'name': 'importedloc',
            'parent_site_code': self.test_state.site_code
        }

        result = import_location(self.domain.name, 'district', data)

        if result['id'] is None:
            self.fail('import failed with error: %s' % result['message'])

        self.assertTrue(data['name'] in self.names_of_locs())
        new_loc = Location.get(result['id'])
        self.assertEqual(new_loc.parent_id, self.test_state._id)

    def test_id_of_invalid_parent_type(self):
        # state can't have outlet as child
        data = {
            'name': 'oops',
            'parent_site_code': self.test_state.site_code
        }

        original_count = len(list(Location.by_domain(self.domain.name)))

        result = import_location(self.domain.name, 'village', data)

        self.assertEqual(result['id'], None)
        self.assertEqual(len(list(Location.by_domain(self.domain.name))), original_count)
        self.assertTrue('Invalid parent type' in result['message'])

    def test_invalid_parent_site_code(self):
        data = {
            'name': 'oops',
            'parent_site_code': 'banana'
        }

        result = import_location(self.domain.name, 'district', data)

        self.assertTrue(
            'Parent with site code banana does not exist' in result['message'],
            result['message']
        )

    def test_invalid_parent_domain(self):
        create_domain('notright')
        parent = make_loc('someparent', domain='notright', type='village')

        data = {
            'name': 'bad parent',
            'outlet_type': 'SHG',
            'site_code': 'wat',
            'parent_site_code': parent.site_code,
        }

        original_count = len(list(Location.by_domain(self.domain.name)))
        result = import_location(self.domain.name, 'outlet', data)
        self.assertEqual(result['id'], None)
        self.assertEqual(len(list(Location.by_domain(self.domain.name))), original_count)
        self.assertTrue('does not exist in this project' in result['message'])

    def test_change_parent(self):
        parent = make_loc('originalparent', type='village')
        existing = make_loc('existingloc', type='outlet', parent=parent)

        new_parent = make_loc('new parent', type='village')
        self.assertNotEqual(parent._id, new_parent._id)
        data = {
            'site_code': existing.site_code,
            'name': existing.name,
            'outlet_type': 'SHG',
            'parent_site_code': new_parent.site_code,
        }

        result = import_location(self.domain.name, 'outlet', data)
        new_loc = Location.get(result['id'])
        self.assertEqual(existing._id, new_loc._id)
        self.assertEqual(new_loc.parent_id, new_parent._id)

    def test_change_to_invalid_parent(self):
        parent = make_loc('original parent', type='village')
        existing = make_loc('existingloc1', type='outlet', parent=parent)

        new_parent = make_loc('new parent', type='state')
        data = {
            'site_code': existing.site_code,
            'name': existing.name,
            'outlet_type': 'SHG',
            'parent_site_code': new_parent.site_code,
        }

        result = import_location(self.domain.name, 'outlet', data)
        self.assertEqual(None, result['id'])
        self.assertTrue('Invalid parent type' in result['message'])
        new_loc = Location.get(existing._id)
        self.assertEqual(existing._id, new_loc._id)
        self.assertEqual(new_loc.parent_id, parent._id)

    def test_updating_existing_location_properties(self):
        existing = make_loc('existingloc2', type='state', domain=self.domain.name)
        existing.save()

        data = {
            'site_code': existing.site_code,
            'name': 'new_name',
        }

        self.assertNotEqual(existing.name, data['name'])

        result = import_location(self.domain.name, 'state', data)
        loc_id = result.get('id', None)
        self.assertIsNotNone(loc_id, result['message'])
        new_loc = Location.get(loc_id)

        self.assertEqual(existing._id, loc_id)
        self.assertEqual(new_loc.name, data['name'])

    def test_given_id_matches_type(self):
        existing = make_loc('existingloc', type='state')

        data = {
            'site_code': existing.site_code,
            'name': 'new_name',
        }

        result = import_location(self.domain.name, 'outlet', data)

        self.assertEqual(result['id'], None)
        self.assertTrue('Existing location type error' in result['message'])

    def test_shouldnt_save_if_no_changes(self):
        existing = make_loc('existingloc', type='outlet', parent=self.test_village)
        existing.site_code = 'wat'
        existing.outlet_type = 'SHG'
        existing.save()

        data = {
            'site_code': existing.site_code,
            'name': existing.name,
            'outlet_type': 'SHG',
        }

        with patch('corehq.apps.locations.forms.LocationForm.save') as save:
            result = import_location(self.domain.name, 'outlet', data)
            self.assertEqual(save.call_count, 0)
            self.assertEqual(result['id'], existing._id)

    def test_should_still_save_if_name_changes(self):
        # name isn't a dynamic property so should test these still
        # get updated alone
        existing = make_loc('existingloc', type='outlet', parent=self.test_village)
        existing.site_code = 'wat'
        existing.outlet_type = 'SHG'
        existing.save()

        data = {
            'site_code': existing.site_code,
            'name': 'newname',
            'outlet_type': 'SHG',
        }

        with patch('corehq.apps.locations.forms.LocationForm.save') as save:
            result = import_location(self.domain.name, 'outlet', data)
            self.assertEqual(save.call_count, 1)
            # id isn't accurate because of the mock, but want to make
            # sure we didn't actually return with None
            self.assertTrue(result['id'] is not None)

    def test_should_import_consumption(self):
        parent = make_loc('originalparent', type='village')
        existing = make_loc('existingloc', type='outlet', parent=parent)
        sp = existing.linked_supply_point()

        data = {
            'site_code': existing.site_code,
            'name': 'existingloc',
            'parent_site_code': parent.site_code,
            'consumption': {'pp': 77},
        }

        import_location(self.domain.name, 'outlet', data)

        self.assertEqual(
            float(get_default_consumption(
                self.domain.name,
                Product.get_by_code(self.domain.name, 'pp')._id,
                'state',
                sp.case_id,
            )),
            77 / DAYS_IN_MONTH
        )

    def test_import_coordinates(self):
        data = {
            'name': 'importedloc',
            'latitude': 55,
            'longitude': -55,
        }

        loc_id = import_location(self.domain.name, 'state', data)['id']

        loc = Location.get(loc_id)

        self.assertEqual(data['latitude'], loc.latitude)
        self.assertEqual(data['longitude'], loc.longitude)
