from django.test.testcases import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from custom.icds_reports.utils import get_location_filter, get_location_level


class TestLocationFilter(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationFilter, cls).setUpClass()
        cls.domain = create_domain('icds-test')
        domain_name = cls.domain.name
        cls.domain_name = domain_name
        location_types = [
            'state',
            'district',
            'block',
            'supervisor',
            'awc'
        ]

        previous_parent = None
        for location_type in location_types:
            previous_parent = LocationType.objects.create(
                domain=domain_name,
                name=location_type,
                parent_type=previous_parent
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

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestLocationFilter, cls).tearDownClass()

    def test_get_location_filter_state(self):
        config = get_location_filter(self.state.location_id, self.domain_name)
        self.assertEqual(config, {'aggregation_level': 2, 'state_id': self.state.location_id})
        self.assertEqual(get_location_level(config['aggregation_level']), 'district')

    def test_get_location_filter_district(self):
        config = get_location_filter(self.district.location_id, self.domain_name)
        self.assertEqual(config, {
            'aggregation_level': 3,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id
        })
        self.assertEqual(get_location_level(config['aggregation_level']), 'block')

    def test_get_location_filter_block(self):
        config = get_location_filter(self.block.location_id, self.domain_name)
        self.assertEqual(config, {
            'aggregation_level': 4,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id
        })
        self.assertEqual(get_location_level(config['aggregation_level']), 'supervisor')

    def test_get_location_filter_supervisor(self):
        config = get_location_filter(self.supervisor.location_id, self.domain_name)
        self.assertEqual(config, {
            'aggregation_level': 5,
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id
        })
        self.assertEqual(get_location_level(config['aggregation_level']), 'awc')

    def test_get_location_filter_awc(self):
        config = get_location_filter(self.awc.location_id, self.domain_name)
        self.assertEqual(config, {
            'aggregation_level': 6,
            'awc_id': self.awc.location_id,
            'supervisor_id': self.supervisor.location_id,
            'block_id': self.block.location_id,
            'district_id': self.district.location_id,
            'state_id': self.state.location_id
        })
        self.assertEqual(get_location_level(config['aggregation_level']), 'awc')
