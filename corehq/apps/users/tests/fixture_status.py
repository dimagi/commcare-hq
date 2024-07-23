from datetime import datetime

from django.test import TestCase

from unittest.mock import MagicMock

from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import clear_domain_names
from corehq.apps.fixtures.models import UserLookupTableStatus, UserLookupTableType
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser, get_fixture_statuses


class TestFixtureStatus(TestCase):

    def setUp(self):
        self._delete_everything()
        self.username = "joe@my-domain.commcarehq.org"
        password = "password"
        self.domain = Domain(name='my-domain')
        self.domain.save()
        self.couch_user = CommCareUser.create(self.domain.name, self.username, password, None, None)
        self.couch_user.save()
        self.web_user = WebUser.create(self.domain.name, "bob@example.com", "123", None, None)
        self.web_user.save()

    def tearDown(self):
        self._delete_everything()

    def _delete_everything(self):
        delete_all_users()
        UserLookupTableStatus.objects.all().delete()
        clear_domain_names('my-domain')

    def test_get_statuses(self):
        no_status = {UserLookupTableType.CHOICES[0][0]: UserLookupTableStatus.DEFAULT_LAST_MODIFIED}
        self.assertEqual(get_fixture_statuses(self.couch_user._id), no_status)

        now = datetime.utcnow()
        UserLookupTableStatus(
            user_id=self.couch_user._id,
            fixture_type=UserLookupTableType.CHOICES[0][0],
            last_modified=now,
        ).save()
        expected_status = {UserLookupTableType.CHOICES[0][0]: now}
        self.assertEqual(get_fixture_statuses(self.couch_user._id), expected_status)

    def test_get_status(self):
        now = datetime.utcnow()
        couch_user = CommCareUser.get_by_username(self.username)
        UserLookupTableStatus(
            user_id=self.couch_user._id,
            fixture_type=UserLookupTableType.CHOICES[0][0],
            last_modified=now,
        ).save()

        self.assertEqual(
            self.couch_user.fixture_status("fake_status"),
            UserLookupTableStatus.DEFAULT_LAST_MODIFIED,
        )
        self.assertEqual(couch_user.fixture_status(UserLookupTableType.CHOICES[0][0]), now)

        UserLookupTableStatus(
            user_id=self.web_user._id,
            fixture_type=UserLookupTableType.CHOICES[0][0],
            last_modified=now,
        ).save()
        self.assertEqual(self.web_user.fixture_status(UserLookupTableType.CHOICES[0][0]), now)

    def test_update_status_set_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "the_depths_of_khazad_dum"
        self.assertEqual(UserLookupTableStatus.objects.all().count(), 0)

        self.couch_user.set_location(fake_location)
        self.web_user.set_location(self.domain.name, fake_location)

        self.assertEqual(UserLookupTableStatus.objects.all().count(), 2)

        user_fixture_status = UserLookupTableStatus.objects.get(user_id=self.couch_user._id)
        self.assertEqual(user_fixture_status.user_id, self.couch_user._id)
        self.assertEqual(user_fixture_status.fixture_type, UserLookupTableType.LOCATION)

        user_fixture_status = UserLookupTableStatus.objects.get(user_id=self.web_user._id)
        self.assertEqual(user_fixture_status.user_id, self.web_user._id)
        self.assertEqual(user_fixture_status.fixture_type, UserLookupTableType.LOCATION)

    def test_update_status_unset_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "the_mines_of_moria"
        self.couch_user.set_location(fake_location)
        self.web_user.set_location(self.domain.name, fake_location)
        couch_user_prev_updated_time = UserLookupTableStatus.objects.get(user_id=self.couch_user._id).last_modified
        web_user_prev_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified

        self.couch_user.unset_location()
        self.web_user.unset_location(self.domain.name)

        couch_user_new_updated_time = UserLookupTableStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(couch_user_new_updated_time > couch_user_prev_updated_time)
        web_user_new_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified
        self.assertTrue(web_user_new_updated_time > web_user_prev_updated_time)

    def test_update_status_reset_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "misty_mountains"
        self.couch_user.set_location(fake_location)
        self.web_user.set_location(self.domain.name, fake_location)
        couch_user_prev_updated_time = UserLookupTableStatus.objects.get(user_id=self.couch_user._id).last_modified
        web_user_prev_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified

        fake_location.location_id = "lonely_mountain"
        self.couch_user.set_location(fake_location)
        self.web_user.reset_locations(self.domain.name, [fake_location.location_id])

        couch_user_new_updated_time = UserLookupTableStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(couch_user_new_updated_time > couch_user_prev_updated_time)
        web_user_new_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified
        self.assertTrue(web_user_new_updated_time > web_user_prev_updated_time)

    def test_unset_location_by_id(self):
        fake_location1 = MagicMock()
        fake_location2 = MagicMock()
        fake_location1.location_id = "misty_mountains"
        fake_location2.location_id = "lonely_mountain"

        self.web_user.set_location(self.domain.name, fake_location1)
        self.web_user.reset_locations(self.domain.name, [fake_location1.location_id, fake_location2.location_id])

        previously_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified

        self.web_user.unset_location_by_id(self.domain.name, fake_location1.location_id)
        new_updated_time = UserLookupTableStatus.objects.get(user_id=self.web_user._id).last_modified
        self.assertTrue(new_updated_time > previously_updated_time)
