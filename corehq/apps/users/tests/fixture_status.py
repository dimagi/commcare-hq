from datetime import datetime
from django.test import TestCase
from mock import MagicMock

from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import UserFixtureStatus, UserFixtureType


class TestFixtureStatus(TestCase):

    def setUp(self):
        self._delete_everything()
        self.username = "joe@my-domain.commcarehq.org"
        password = "password"
        self.domain = Domain(name='my-domain')
        self.domain.save()
        self.couch_user = CommCareUser.create(self.domain.name, self.username, password)
        self.couch_user.save()

    def tearDown(self):
        self._delete_everything()

    def _delete_everything(self):
        delete_all_users()
        UserFixtureStatus.objects.all().delete()

    def test_get_statuses(self):
        no_status = {UserFixtureType.CHOICES[0][0]: UserFixtureStatus.DEFAULT_LAST_MODIFIED}
        self.assertEqual(self.couch_user._get_fixture_statuses(), no_status)

        now = datetime.utcnow()
        UserFixtureStatus(
            user_id=self.couch_user._id,
            fixture_type=UserFixtureType.CHOICES[0][0],
            last_modified=now,
        ).save()
        expected_status = {UserFixtureType.CHOICES[0][0]: now}
        self.assertEqual(self.couch_user._get_fixture_statuses(), expected_status)

    def test_get_status(self):
        now = datetime.utcnow()
        couch_user = CommCareUser.get_by_username(self.username)
        UserFixtureStatus(
            user_id=self.couch_user._id,
            fixture_type=UserFixtureType.CHOICES[0][0],
            last_modified=now,
        ).save()

        self.assertEqual(self.couch_user.fixture_status("fake_status"), UserFixtureStatus.DEFAULT_LAST_MODIFIED)
        self.assertEqual(couch_user.fixture_status(UserFixtureType.CHOICES[0][0]), now)

    def test_update_status_set_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "the_depths_of_khazad_dum"
        fake_location.group_id = "the_depths_of_khazad_dum"
        self.assertEqual(UserFixtureStatus.objects.all().count(), 0)

        self.couch_user.set_location(fake_location)

        self.assertEqual(UserFixtureStatus.objects.all().count(), 1)
        user_fixture_status = UserFixtureStatus.objects.first()

        self.assertEqual(user_fixture_status.user_id, self.couch_user._id)
        self.assertEqual(user_fixture_status.fixture_type, UserFixtureType.LOCATION)

    def test_update_status_unset_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "the_mines_of_moria"
        fake_location.group_id = "the_mines_of_moria"
        self.couch_user.set_location(fake_location)
        previously_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified

        self.couch_user.unset_location()

        new_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(new_updated_time > previously_updated_time)

    def test_update_status_reset_location(self):
        fake_location = MagicMock()
        fake_location.location_id = "misty_mountains"
        fake_location.group_id = "misty_mountains"
        self.couch_user.set_location(fake_location)
        previously_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified

        fake_location.location_id = "lonely_mountain"
        fake_location.group_id = "lonely_mountain"
        self.couch_user.set_location(fake_location)

        new_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(new_updated_time > previously_updated_time)
