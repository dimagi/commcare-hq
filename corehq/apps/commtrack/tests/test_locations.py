from corehq.apps.locations.models import SQLLocation
from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc, FIXED_USER
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.tests.utils import run_with_all_backends


def _count_locations(domain):
    return SQLLocation.active_objects.filter(domain=domain).count()


def _count_root_locations(domain):
    return SQLLocation.active_objects.root_nodes().filter(domain=domain).count()


class LocationsTest(CommTrackTest):
    user_definitions = [FIXED_USER]

    def setUp(self):
        super(LocationsTest, self).setUp()
        self.accessor = SupplyInterface(self.domain.name)
        self.user = self.users[0]

    @run_with_all_backends
    def test_sync(self):
        test_state = make_loc(
            'teststate',
            type='state',
            parent=self.user.location
        )
        test_village = make_loc(
            'testvillage',
            type='village',
            parent=test_state
        )

        try:
            sql_village = SQLLocation.objects.get(
                name='testvillage',
                domain=self.domain.name,
            )

            self.assertEqual(sql_village.name, test_village.name)
            self.assertEqual(sql_village.domain, test_village.domain)
        except SQLLocation.DoesNotExist:
            self.fail("Synced SQL object does not exist")

    @run_with_all_backends
    def test_archive(self):
        test_state = make_loc(
            'teststate',
            type='state',
            parent=self.user.location
        )
        test_state.save()

        original_count = _count_locations(self.domain.name)

        loc = self.user.sql_location
        loc.archive()

        # it should also archive children
        self.assertEqual(
            _count_locations(self.domain.name),
            original_count - 2
        )
        self.assertEqual(
            _count_root_locations(self.domain.name),
            0
        )

        loc.unarchive()

        # and unarchive children
        self.assertEqual(
            _count_locations(self.domain.name),
            original_count
        )
        self.assertEqual(
            _count_root_locations(self.domain.name),
            1
        )

    @run_with_all_backends
    def test_archive_flips_sp_cases(self):
        loc = make_loc('someloc').sql_location
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
            'test_loc',
            type='state',
            parent=self.user.location
        )
        test_loc.save()

        original_count = _count_locations(self.domain.name)

        loc = self.user.sql_location
        loc.full_delete()

        # it should also delete children
        self.assertEqual(
            _count_locations(self.domain.name),
            original_count - 2
        )
        self.assertEqual(
            _count_root_locations(self.domain.name),
            0
        )
        # permanently gone from sql db
        self.assertEqual(
            len(SQLLocation.objects.all()),
            0
        )

    @run_with_all_backends
    def test_delete_closes_sp_cases(self):
        loc = make_loc('test_loc').sql_location
        sp = loc.linked_supply_point()

        self.assertFalse(sp.closed)
        loc.full_delete()
        sp = self.accessor.get_supply_point(sp.case_id)
        self.assertTrue(sp.closed)
