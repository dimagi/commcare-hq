from django.test import TestCase
from mock import MagicMock
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import UserFixtureStatus, UserFixtureType

class UpdateTestCase(TestCase):

    def setUp(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        User.objects.all().delete()
        self.username = "joe@my-domain.commcarehq.org"
        password = "password"
        self.domain = Domain(name='my-domain')
        self.domain.save()
        self.couch_user = CommCareUser.create(self.domain.name, self.username, password)
        self.couch_user.save()
        
    def testAddRemovePhoneNumbers(self):
        """ 
        test that a basic couch user gets created properly after 
        saving a django user programmatically
        """
        self.couch_user.add_phone_number('123123123')
        self.assertEqual(self.couch_user.phone_numbers, ['123123123'])
        self.couch_user.add_phone_number('321321321')
        self.assertEqual(self.couch_user.phone_numbers, ['123123123', '321321321'])

    def testChangeUsername(self):
        new_username = 'joe.shmoe@domain.com'
        self.assertEqual(CouchUser.get_by_username(self.username).user_id, self.couch_user.user_id)
        self.assertEqual(User.objects.filter(username=self.username).count(), 1)
        self.couch_user.change_username(new_username)
        self.assertEqual(CouchUser.get_by_username(self.username), None)
        self.assertEqual(CouchUser.get_by_username(new_username).user_id, self.couch_user.user_id)
        self.assertEqual(self.couch_user.get_django_user().username, new_username)
        self.assertEqual(User.objects.filter(username=new_username).count(), 1)
        self.assertEqual(User.objects.get(username=new_username).id, self.couch_user.get_django_user().id)
        self.assertEqual(User.objects.filter(username=self.username).count(), 0)


class UpdateFixtureStatus(UpdateTestCase):

    def testSetLocation(self):
        fake_location = MagicMock()
        fake_location._id = "the_depths_of_khazad_dum"
        self.assertEqual(UserFixtureStatus.objects.all().count(), 0)

        self.couch_user.set_location(fake_location)

        self.assertEqual(UserFixtureStatus.objects.all().count(), 1)
        user_fixture_status = UserFixtureStatus.objects.first()

        self.assertEqual(user_fixture_status.user_id, self.couch_user._id)
        self.assertEqual(user_fixture_status.fixture_type, UserFixtureType.LOCATION)

    def testUnSetLocation(self):
        fake_location = MagicMock()
        fake_location._id = "the_mines_of_moria"
        self.couch_user.set_location(fake_location)
        previously_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified

        self.couch_user.unset_location()

        new_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(new_updated_time > previously_updated_time)

    def testResetLocation(self):
        fake_location = MagicMock()
        fake_location._id = "misty_mountains"
        self.couch_user.set_location(fake_location)
        previously_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified

        fake_location._id = "lonely_mountain"
        self.couch_user.set_location(fake_location)

        new_updated_time = UserFixtureStatus.objects.get(user_id=self.couch_user._id).last_modified
        self.assertTrue(new_updated_time > previously_updated_time)

#    def testUpdateDjangoUser(self):
#        """
#        test that a basic couch user gets created properly after
#        saving a django user programmatically
#        """
#        self.user.first_name = "update_first"
#        self.user.last_name = "update_last"
#        self.user.save()
#        self.assertEqual(self.user.get_profile().get_couch_user().django_user.first_name, 'update_first')
#        self.assertEqual(self.user.get_profile().get_couch_user().django_user.last_name, 'update_last')
#
