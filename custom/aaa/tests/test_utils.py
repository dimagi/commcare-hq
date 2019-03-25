from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from custom.aaa.const import MINISTRY_MWCD, ALL, MINISTRY_MOHFW
from custom.aaa.utils import build_location_filters


class TestUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUtils, cls).setUpClass()
        cls.domain = create_domain('reach-test')
        domain_name = cls.domain.name
        cls.domain_name = domain_name
        location_types = [
            {'type': 'state', 'parent': None},
            {'type': 'district', 'parent': 'state'},
            {'type': 'block', 'parent': 'district'},
            {'type': 'supervisor', 'parent': 'block'},
            {'type': 'awc', 'parent': 'supervisor'},
            {'type': 'taluka', 'parent': 'district'},
            {'type': 'phc', 'parent': 'taluka'},
            {'type': 'sc', 'parent': 'phc'},
            {'type': 'village', 'parent': 'sc'},
        ]

        for location_type in location_types:
            if location_type['parent'] is not None:
                parent_tape = LocationType.objects.get(domain=domain_name, name=location_type['parent'])
            else:
                parent_tape = None
            LocationType.objects.create(
                domain=domain_name,
                name=location_type['type'],
                parent_type=parent_tape
            )

        cls.state = SQLLocation.objects.create(
            name='Test State',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='state')
        )
        cls.district = SQLLocation.objects.create(
            name='Test District',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='district'),
            parent=cls.state,
        )
        cls.block = SQLLocation.objects.create(
            name='Test Block',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='block'),
            parent=cls.district
        )
        cls.supervisor = SQLLocation.objects.create(
            name='Test Supervisor',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='supervisor'),
            parent=cls.block
        )
        cls.awc = SQLLocation.objects.create(
            name='Test AWC',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='awc'),
            parent=cls.supervisor
        )
        cls.taluka = SQLLocation.objects.create(
            name='Test Taluka',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='taluka'),
            parent=cls.district,
        )
        cls.phc = SQLLocation.objects.create(
            name='Test PHC',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='phc'),
            parent=cls.taluka
        )
        cls.sc = SQLLocation.objects.create(
            name='Test SC',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='sc'),
            parent=cls.phc
        )
        cls.village = SQLLocation.objects.create(
            name='Test Village',
            domain=domain_name,
            location_type=LocationType.objects.get(domain=domain_name, name='village'),
            parent=cls.sc
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestUtils, cls).tearDownClass()

    def test_build_location_filters_for_village_MOHFW(self):
        expected_output = {
            'village_id': self.village.location_id,
            'sc_id': self.sc.location_id,
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.village.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_sc_MOHFW(self):
        expected_output = {
            'village_id': ALL,
            'sc_id': self.sc.location_id,
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.sc.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_phc_MOHFW(self):
        expected_output = {
            'sc_id': ALL,
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.phc.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_taluka_MOHFW(self):
        expected_output = {
            'phc_id': ALL,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.taluka.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_district_MOHFW(self):
        expected_output = {
            'taluka_id': ALL,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.district.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_state_MOHFW(self):
        expected_output = {
            'district_id': ALL,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.state.location_id, MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_national_MOHFW(self):
        expected_output = {
            'state_id': ALL,
        }
        result = build_location_filters('', MINISTRY_MOHFW)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_awc_MWCD(self):
        expected_output = {
            'awc_id': self.awc.location_id,
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.awc.location_id, MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_supervisor_MWCD(self):
        expected_output = {
            'awc_id': ALL,
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.supervisor.location_id, MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_block_MWCD(self):
        expected_output = {
            'supervisor_id': ALL,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.block.location_id, MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_district_MWCD(self):
        expected_output = {
            'block_id': ALL,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.district.location_id, MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_state_MWCD(self):
        expected_output = {
            'district_id': ALL,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.state.location_id, MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_national_MWCD(self):
        expected_output = {
            'state_id': ALL,
        }
        result = build_location_filters('', MINISTRY_MWCD)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_village_without_child_MOHFW(self):
        expected_output = {
            'village_id': self.village.location_id,
            'sc_id': self.sc.location_id,
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.village.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_sc_without_child_MOHFW(self):
        expected_output = {
            'sc_id': self.sc.location_id,
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.sc.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_phc_without_child_MOHFW(self):
        expected_output = {
            'phc_id': self.phc.location_id,
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.phc.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_taluka_without_child_MOHFW(self):
        expected_output = {
            'taluka_id': self.taluka.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.taluka.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_district_without_child_MOHFW(self):
        expected_output = {
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.district.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_state_without_child_MOHFW(self):
        expected_output = {
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.state.location_id, MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_national_without_child_MOHFW(self):
        expected_output = {}
        result = build_location_filters('', MINISTRY_MOHFW, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_awc_without_child_MWCD(self):
        expected_output = {
            'awc_id': self.awc.location_id,
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.awc.location_id, MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_supervisor_without_child_MWCD(self):
        expected_output = {
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.supervisor.location_id, MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_block_without_child_MWCD(self):
        expected_output = {
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.block.location_id, MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_district_without_child_MWCD(self):
        expected_output = {
            'district_id': self.district.location_id,
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.district.location_id, MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_state_without_child_MWCD(self):
        expected_output = {
            'state_id': self.state.location_id,
        }
        result = build_location_filters(self.state.location_id, MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)

    def test_build_location_filters_for_national_without_child_MWCD(self):
        expected_output = {}
        result = build_location_filters('', MINISTRY_MWCD, with_child=False)
        self.assertDictEqual(result, expected_output)