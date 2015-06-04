from ..models import Location, SQLLocation
from .test_locations import LocationTestBase
from .util import make_loc


class TestReupholster(LocationTestBase):
    """
    These tests were written to drive removal of sepecific queries. It
    is safe to delete this when the reuholstering of Location is done
    and somone has written test coverage for the methods used in here.
    """
    def setUp(self):
        super(TestReupholster, self).setUp()
        self.state = make_loc("Florida", type='state')
        self.district = make_loc("Duval", type='district', parent=self.state)
        self.block = make_loc("Jacksonville", type='block', parent=self.district)

    def test_replace_all_ids(self):
        original_result = set([r['id'] for r in Location.get_db().view(
            'locations/by_name',
            reduce=False,
        ).all()])

        new_result = set(SQLLocation.objects.ids())

        self.assertEqual(original_result, new_result)

    def test_all_for_domain_by_type(self):
        original_result = set([r['id'] for r in Location.get_db().view(
            'locations/by_type',
            reduce=False,
            startkey=[self.domain.name],
            endkey=[self.domain.name, {}],
        ).all()])

        new_result = set(SQLLocation.objects.domain(self.domain.name).ids())

        self.assertEqual(original_result, new_result)

    def _blocks_by_type(self, loc_id, reduce=False):
        return Location.get_db().view('locations/by_type',
            reduce=reduce,
            startkey=[self.domain.name, 'block', loc_id],
            endkey=[self.domain.name, 'block', loc_id, {}],
        )

    def test_count_by_type(self):
        from custom.intrahealth.report_calcs import _locations_per_type
        original_result = (self._blocks_by_type(self.state._id, reduce=True)
                           .one()['value'])
        new_result = _locations_per_type(self.domain.name, 'block', self.state)
        self.assertEqual(original_result, new_result)

    def test_filter_by_type(self):
        original_result = [r['id'] for r in self._blocks_by_type(self.state._id)]

        new_result = (self.state.sql_location
                      .get_descendants(include_self=True)
                      .filter(domain=self.domain.name,
                              location_type__name='block')
                      .ids())

        self.assertEqual(original_result, list(new_result))

    def test_filter_by_type_no_root(self):
        original_result = [r['id'] for r in self._blocks_by_type(None)]

        new_result = (SQLLocation.objects
                      .filter(domain=self.domain.name,
                              location_type__name='block')
                      .ids())

        self.assertEqual(original_result, list(new_result))


class TestPath(LocationTestBase):
    def test_path(self):
        locs = [
            ('Mass', 'state'),
            ('Suffolk', 'district'),
            ('Boston', 'block'),
        ]
        parent = None
        for name, type_ in locs:
            parent = make_loc(name, type=type_, parent=parent)
        boston = parent
        self.assertEqual(boston.path, boston.sql_location.path)
