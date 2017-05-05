import datetime
from django.test import override_settings, TestCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from corehq.apps.repeaters.models import RepeatRecord

from custom.enikshay.integrations.bets.repeaters import UserRepeater


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class UserRepeaterTest(TestCase):
    domain = 'user-repeater'

    def setUp(self):
        super(UserRepeaterTest, self).setUp()
        self.repeater = UserRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(UserRepeaterTest, self).tearDown()
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
