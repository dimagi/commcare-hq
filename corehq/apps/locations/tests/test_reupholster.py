from .test_locations import LocationTestBase
from .util import make_loc

    def test_site_codes_for_domain(self):
        original_result = set([r['key'][1] for r in Location.get_db().view(
            'locations/prop_index_site_code',
            reduce=False,
            startkey=[self.domain.name],
            endkey=[self.domain.name, {}],
        ).all()])

        new_result = {
            code.lower() for code in
            (SQLLocation.objects.filter(domain=self.domain)
                                .values_list('site_code', flat=True))
        }

        self.assertEqual(original_result, new_result)

    def test_by_site_code_exists(self):
        couch = _couch_by_site_code(self.domain.name, self.district.site_code)
        sql = _sql_by_site_code(self.domain.name, self.district.site_code)
        self.assertEqual(couch, sql)
        self.assertNotEqual(None, couch)

    def test_by_site_code_doesnt_exist(self):
        couch = _couch_by_site_code(self.domain.name, 'nonexistant_code')
        sql = _sql_by_site_code(self.domain.name, 'nonexistant_code')
        self.assertEqual(couch, sql)
        self.assertEqual(None, couch)


def _couch_by_site_code(domain, site_code):
    # This view coerces the site code to lowercase, so you must also
    # make sure your code is lowercase.  This means that this hasn't been
    # working for all locations: loc.by_site_code(loc.domain, loc.site_code)
    result = Location.get_db().view(
        'locations/prop_index_site_code',
        reduce=False,
        startkey=[domain, site_code.lower()],
        endkey=[domain, site_code.lower(), {}],
    ).first()
    return Location.get(result['id']) if result else None


def _sql_by_site_code(domain, site_code):
    try:
        return (SQLLocation.objects.get(domain=domain, site_code=site_code)
                .couch_location)
    except SQLLocation.DoesNotExist:
        return None


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
