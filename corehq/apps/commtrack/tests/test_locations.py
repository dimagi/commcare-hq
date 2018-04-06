from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.commtrack.tests.util import make_loc, bootstrap_domain, bootstrap_location_types
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.tests.utils import run_with_all_backends


def _count_locations(domain):
    return SQLLocation.active_objects.filter(domain=domain).count()


def _count_root_locations(domain):
    return SQLLocation.active_objects.root_nodes().filter(domain=domain).count()


class LocationsTest(TestCase):
    domain = 'westworld'

    @classmethod
    def setUpClass(cls):
        super(LocationsTest, cls).setUpClass()
        delete_all_users()
        cls.domain_obj = bootstrap_domain(cls.domain)
        bootstrap_location_types(cls.domain)

    @classmethod
    def tearDownClass(cls):
        super(LocationsTest, cls).tearDownClass()
        cls.domain_obj.delete()  # domain delete cascades to everything else
        delete_all_users()

    def setUp(self):
        super(LocationsTest, self).setUp()
        self.user = CommCareUser.create(domain=self.domain, username='d.abernathy', password='123')
        self.loc = make_loc('mariposa_saloon', domain=self.domain)
        self.user.set_location(self.loc)

    def tearDown(self):
        self.user.delete()
        SQLLocation.objects.all().delete()
        super(LocationsTest, self).tearDown()

    @run_with_all_backends
    def test_archive(self):
        test_state = make_loc(
            'pariah',
            type='state',
            parent=self.user.location,
            domain=self.domain,
        )
        test_state.save()

        original_count = _count_locations(self.domain)

        loc = self.user.sql_location
        loc.archive()

        # it should also archive children
        self.assertEqual(
            _count_locations(self.domain),
            original_count - 2
        )
        self.assertEqual(
            _count_root_locations(self.domain),
            0
        )

        loc.unarchive()

        # and unarchive children
        self.assertEqual(
            _count_locations(self.domain),
            original_count
        )
        self.assertEqual(
            _count_root_locations(self.domain),
            1
        )

    @run_with_all_backends
    def test_archive_flips_sp_cases(self):
        loc = make_loc('las_mudas', domain=self.domain).sql_location
        sp = loc.linked_supply_point()

        self.assertFalse(sp.closed)
        loc.archive()
        sp = loc.linked_supply_point()
        self.assertTrue(sp.closed)

        loc.unarchive()
        sp = loc.linked_supply_point()
        self.assertFalse(sp.closed)

    @run_with_all_backends
    def test_full_delete(self):
        test_loc = make_loc(
            'abernathy_ranch',
            type='state',
            parent=self.user.location,
            domain=self.domain,
        )
        test_loc.save()

        original_count = _count_locations(self.domain)

        loc = self.user.sql_location
        loc.full_delete()

        # it should also delete children
        self.assertEqual(
            _count_locations(self.domain),
            original_count - 2
        )
        self.assertEqual(
            _count_root_locations(self.domain),
            0
        )
        # permanently gone from sql db
        self.assertEqual(
            len(SQLLocation.objects.all()),
            0
        )

    @run_with_all_backends
    def test_delete_closes_sp_cases(self):
        accessor = SupplyInterface(self.domain)
        loc = make_loc('ghost_nation', domain=self.domain).sql_location
        sp = loc.linked_supply_point()
        self.assertFalse(sp.closed)
        loc.full_delete()
        sp = accessor.get_supply_point(sp.case_id)
        self.assertTrue(sp.closed)
