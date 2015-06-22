import itertools
from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain

from ..models import Location
from .test_locations import LocationTestBase
from .util import make_loc, delete_all_locations


def _couch_root_locations(domain):
    results = Location.get_db().view('locations/hierarchy',
                                     startkey=[domain], endkey=[domain, {}],
                                     reduce=True, group_level=2)
    ids = [res['key'][-1] for res in results]
    locs = [Location.get(id) for id in ids]
    return [loc for loc in locs if not loc.is_archived]


def _key_bounds(location):
    startkey = list(itertools.chain([location.domain], location.path, ['']))
    endkey = list(itertools.chain(startkey[:-1], [{}]))
    return startkey, endkey


def _couch_descendants(location):
    """return list of all locations that have this location as an ancestor"""
    startkey, endkey = _key_bounds(location)
    return location.view('locations/hierarchy', startkey=startkey,
                         endkey=endkey, reduce=False, include_docs=True).all()


def _couch_children(location):
    """return list of immediate children of this location"""
    startkey, endkey = _key_bounds(location)
    depth = len(location.path) + 2  # 1 for domain, 1 for next location level
    q = location.view('locations/hierarchy', startkey=startkey, endkey=endkey, group_level=depth)
    keys = [e['key'] for e in q if len(e['key']) == depth]
    return location.view('locations/hierarchy', keys=keys, reduce=False, include_docs=True).all()


class TestReupholster(TestCase):
    """
    These tests were written to drive removal of sepecific queries. It
    is safe to delete this when the reuholstering of Location is done
    and somone has written test coverage for the methods used in here.
    """
    @classmethod
    def setUpClass(cls):
        delete_all_locations()
        cls.domain = create_domain('locations-test')
        cls.domain.locations_enabled = True
        bootstrap_location_types(cls.domain.name)

        cls.state = make_loc("Florida", type='state')
        cls.district = make_loc("Duval", type='district', parent=cls.state)
        cls.block = make_loc("Jacksonville", type='block', parent=cls.district)

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()

    def test_root_locations(self):
        self.assertEqual(
            set(_couch_root_locations(self.domain.name)),
            set(Location.root_locations(self.domain.name)),
        )

    def test_descendants(self):
        self.assertEqual(
            _couch_descendants(self.state),
            self.state.descendants,
        )

    def test_children(self):
        self.assertEqual(
            _couch_children(self.state),
            self.state.children,
        )


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
