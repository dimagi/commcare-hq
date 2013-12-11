from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.locations.models import Location
from corehq.apps.locations.bulk import import_location
from mock import patch


class LocationImportTest(CommTrackTest):
    def names_of_locs(self):
        return [loc.name for loc in Location.by_domain(self.domain.name)]

    def test_import_new_top_level_location(self):
        data = {
            'name': 'importedloc'
        }

        import_location(self.domain.name, 'state', data)

        self.assertTrue(data['name'] in self.names_of_locs())

    def test_import_with_existing_parent_by_id(self):
        parent = make_loc('sillyparents')
        parent.location_type = 'state'  # state can't have outlet as child
        parent.save()

        data = {
            'name': 'importedloc',
            'parent_id': parent._id
        }

        result = import_location(self.domain.name, 'district', data)

        if result['id'] is None:
            self.fail('import failed with error: %s' % result['message'])

        self.assertTrue(data['name'] in self.names_of_locs())
        new_loc = Location.get(result['id'])
        self.assertEqual(new_loc.parent_id, parent._id)

    def test_id_of_invalid_parent_type(self):
        parent = make_loc('sillyparents')
        parent.location_type = 'state'  # state can't have outlet as child
        parent.save()

        data = {
            'name': 'oops',
            'outlet_type': 'SHG',
            'parent_id': parent._id
        }

        original_count = len(list(Location.by_domain(self.domain.name)))

        try:
            result = import_location(self.domain.name, 'outlet', data)
        except Exception as e:
            self.fail("import_location raised an error: %s" % e)

        self.assertEqual(result['id'], None)
        self.assertEqual(len(list(Location.by_domain(self.domain.name))), original_count)
        self.assertTrue('Invalid parent type' in result['message'])

    def test_invalid_parent_id(self):
        data = {
            'name': 'oops',
            'outlet_type': 'SHG',
            'parent_id': 'banana'
        }

        try:
            result = import_location(self.domain.name, 'outlet', data)
        except Exception as e:
            self.fail("import_location raised an error: %s" % e)

        self.assertTrue('Parent with id banana does not exist' in result['message'])

    def test_updating_existing_location_properties(self):
        parent = make_loc('sillyparents')
        parent.location_type = 'village'
        parent.save()
        existing = make_loc('existingloc', parent=parent)
        existing.location_type = 'outlet'
        existing.save()

        data = {
            'id': existing._id,
            'name': existing.name,
            'site_code': 'wat',
            'outlet_type': 'SHG'
        }

        self.assertNotEqual(existing.site_code, data['site_code'])

        loc_id = import_location(self.domain.name, 'outlet', data).get('id', None)
        new_loc = Location.get(loc_id)

        self.assertEqual(existing._id, loc_id)
        self.assertEqual(new_loc.site_code, data['site_code'])

    def test_given_id_matches_type(self):
        existing = make_loc('existingloc')
        existing.location_type = 'state'
        existing.save()

        data = {
            'id': existing._id,
            'name': 'new_name',
        }

        result = import_location(self.domain.name, 'outlet', data)

        self.assertEqual(result['id'], None)
        self.assertTrue('Existing location type error' in result['message'])

    def test_shouldnt_save_if_no_changes(self):
        parent = make_loc('sillyparents')
        parent.location_type = 'village'
        parent.save()
        existing = make_loc('existingloc', parent=parent)
        existing.location_type = 'outlet'
        existing.site_code = 'wat'
        existing.outlet_type = 'SHG'
        existing.save()

        data = {
            'id': existing._id,
            'name': existing.name,
            'site_code': 'wat',
            'outlet_type': 'SHG',
        }

        with patch('corehq.apps.locations.forms.LocationForm.save') as save:
            result = import_location(self.domain.name, 'outlet', data)
            self.assertEqual(save.call_count, 0)
            self.assertEqual(result['id'], existing._id)

    def test_should_still_save_if_name_changes(self):
        # name isn't a dynamic property so should test these still
        # get updated alone
        parent = make_loc('sillyparents')
        parent.location_type = 'village'
        parent.save()
        existing = make_loc('existingloc', parent=parent)
        existing.location_type = 'outlet'
        existing.site_code = 'wat'
        existing.outlet_type = 'SHG'
        existing.save()

        data = {
            'id': existing._id,
            'name': 'newname',
            'site_code': 'wat',
            'outlet_type': 'SHG',
        }

        with patch('corehq.apps.locations.forms.LocationForm.save') as save:
            result = import_location(self.domain.name, 'outlet', data)
            self.assertEqual(save.call_count, 1)
            # id isn't accurate because of the mock, but want to make
            # sure we didn't actually return with None
            self.assertTrue(result['id'] is not None)
