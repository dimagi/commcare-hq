from ..models import Location, SQLLocation
from .test_locations import LocationTestBase
from .util import make_loc


class TestReupholster(LocationTestBase):
    def setUp(self):
        super(TestReupholster, self).setUp()
        locs = [
            ('Florida', 'state'),
            ('Duval', 'district'),
            ('Jacksonville', 'block'),
        ]
        parent = None
        for name, type_ in locs:
            parent = make_loc(name, type=type_, parent=parent)

    def test_replace_all_ids(self):
        original_result = set([r['id'] for r in Location.get_db().view(
            'locations/by_name',
            reduce=False,
        ).all()])

        new_result = set(SQLLocation.all_objects.ids())

        self.assertEqual(original_result, new_result)


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
