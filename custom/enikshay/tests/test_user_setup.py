from django.test import TestCase, override_settings
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from .utils import setup_enikshay_locations
from ..users.setup_utils import get_allowable_user_data_types, validate_nikshay_code


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestUserSetupUtils(TestCase):
    domain = 'enikshay-user-setup'

    @classmethod
    def setUpClass(cls):
        super(TestUserSetupUtils, cls).setUpClass()
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()
        cls.location_types, cls.locations = setup_enikshay_locations(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestUserSetupUtils, cls).tearDownClass()

    # def setUp(self):
    #     super(TestUserSetupUtils, self).setUp()

    # def tearDown(self):
    #     super(TestUserSetupUtils, self).tearDown()

    def make_location(self, name, loc_type, parent):
        loc = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=self.location_types[loc_type],
            parent=self.locations[parent],
            metadata={'nikshay_code': name},
        )
        self.addCleanup(loc.delete)
        return loc

    def test_get_allowable_user_data_types(self):
        user = CommCareUser.create(
            self.domain,
            "jon-snow@user",
            "123",
        )
        self.addCleanup(user.delete)
        user.set_location(self.locations['DTO'])
        self.assertEqual(user.get_sql_location(self.domain).location_type.name, 'dto')
        self.assertEqual(get_allowable_user_data_types(self.domain, user), ['dto', 'deo'])
        user.unset_location(self.domain)
        user.get_sql_location.reset_cache(user)
        user.set_location(self.locations['STO'])
        self.assertEqual(get_allowable_user_data_types(self.domain, user), ['sto'])

    def test_validate_nikshay_code(self):
        loc1 = self.make_location('winterfell', 'tu', 'DTO')
        loc2 = self.make_location('castle_black', 'tu', 'DTO')
        # TODO make this trigger on save?
        self.assertTrue(validate_nikshay_code(self.domain, loc2))
        loc2.metadata['nikshay_code'] = loc1.metadata['nikshay_code']
        self.assertFalse(validate_nikshay_code(self.domain, loc2))
