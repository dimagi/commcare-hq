import datetime
from django.test import override_settings, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import CommCareUser
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from corehq.apps.repeaters.models import RepeatRecord

from custom.enikshay.integrations.bets.repeaters import BETSUserRepeater, BETSLocationRepeater


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSUserRepeaterTest(TestCase):
    domain = 'user-repeater'

    def setUp(self):
        super(BETSUserRepeaterTest, self).setUp()
        self.repeater = BETSUserRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(BETSUserRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.datetime.utcnow())

    def make_user(self, username):
        user = CommCareUser.create(
            self.domain,
            "{}@{}.commcarehq.org".format(username, self.domain),
            "123",
        )
        self.addCleanup(user.delete)
        return user

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        user = self.make_user("bselmy")
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            record.get_payload(),
            {
                'id': user._id,
                'username': user.username,
                'first_name': '',
                'last_name': '',
                'default_phone_number': None,
                'user_data': {'commcare_project': self.domain},
                'groups': [],
                'phone_numbers': [],
                'email': '',
                'resource_uri': '/a/user-repeater/api/v0.5/user/{}/'.format(user._id),
            }
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSLocationRepeaterTest(TestCase):
    domain = 'location-repeater'

    def setUp(self):
        super(BETSLocationRepeaterTest, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.repeater = BETSLocationRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()
        self.location_type = LocationType.objects.create(
            domain=self.domain,
            name="city",
        )

    def tearDown(self):
        super(BETSLocationRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()
        self.domain_obj.delete()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.datetime.utcnow())

    def make_location(self, name):
        location = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=self.location_type,
        )
        self.addCleanup(location.delete)
        return location

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        location = self.make_location('kings_landing')
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            record.get_payload(),
            {
                '_id': location.location_id,
                'doc_type': 'Location',
                'domain': self.domain,
                'external_id': None,
                'is_archived': False,
                'last_modified': location.last_modified.isoformat(),
                'latitude': None,
                'lineage': [],
                'location_id': location.location_id,
                'location_type': 'city',
                'longitude': None,
                'metadata': {},
                'name': location.name,
                'parent_location_id': None,
                'site_code': location.site_code,
            }
        )
