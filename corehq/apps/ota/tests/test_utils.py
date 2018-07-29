from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.util import format_username
from corehq.apps.domain.models import Domain
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from casexml.apps.phone.models import OTARestoreWebUser, OTARestoreCommCareUser

from corehq.apps.ota.utils import is_permitted_to_restore, get_restore_user


class RestorePermissionsTest(LocationHierarchyTestCase):
    domain = 'goats'
    other_domain = 'sheep'
    location_type_names = ['country', 'state']
    location_structure = [
        ('usa', [
            ('ma', []),
        ]),
        ('canada', [
            ('montreal', []),
        ]),
    ]

    @classmethod
    def setUpClass(cls):
        super(RestorePermissionsTest, cls).setUpClass()

        cls.other_project = Domain(name=cls.other_domain)
        cls.other_project.save()

        cls.web_user = WebUser.create(
            username='billy@goats.com',
            domain=cls.domain,
            password='***',
        )
        cls.super_user = WebUser.create(
            username='super@woman.com',
            domain=cls.other_domain,
            password='***',
        )
        cls.super_user.is_superuser = True
        cls.super_user.save()
        cls.commcare_user = CommCareUser.create(
            username=format_username('super', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.no_edit_commcare_user = CommCareUser.create(
            username=format_username('noedit', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.location_user = CommCareUser.create(
            username=format_username('location', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.wrong_location_user = CommCareUser.create(
            username=format_username('wrong-location', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.web_location_user = WebUser.create(
            username='web-location@location.com',
            domain=cls.domain,
            password='***',
        )

        cls.commcare_user.set_location(cls.locations['usa'])
        cls.web_location_user.set_location(cls.domain, cls.locations['usa'])
        cls.no_edit_commcare_user.set_location(cls.locations['usa'])
        cls.location_user.set_location(cls.locations['ma'])
        cls.wrong_location_user.set_location(cls.locations['montreal'])

        cls.restrict_user_to_assigned_locations(cls.commcare_user)
        cls.restrict_user_to_assigned_locations(cls.web_location_user)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.other_project.delete()
        super(RestorePermissionsTest, cls).tearDownClass()

    def test_commcare_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            None,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_wrong_domain(self):
        is_permitted, message = is_permitted_to_restore(
            'wrong-domain',
            self.commcare_user,
            None,
        )
        self.assertFalse(is_permitted)
        self.assertRegexpMatches(message, 'was not in the domain')

    def test_web_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            None,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)

    def test_web_user_as_other_web_user(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.web_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_as_self(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_self(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.web_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_super_user_as_user_other_domain(self):
        """
        Superusers should be able to restore as other mobile users even if it's the wrong domain
        """
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.super_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_as_user_disallow_no_edit_data(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.no_edit_commcare_user,
            self.location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegexpMatches(message, 'does not have permission')

    def test_commcare_user_as_user_in_location(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.location_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.wrong_location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegexpMatches(message, 'not in allowed locations')

    def test_web_user_as_user_in_location(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_location_user,
            self.location_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_location_user,
            self.wrong_location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegexpMatches(message, 'not in allowed locations')


class GetRestoreUserTest(TestCase):

    domain = 'goats'
    other_domain = 'sheep'

    @classmethod
    def setUpClass(cls):
        super(GetRestoreUserTest, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        cls.other_project = Domain(name=cls.other_domain)
        cls.other_project.save()

        cls.web_user = WebUser.create(
            username='billy@goats.com',
            domain=cls.domain,
            password='***',
        )
        cls.commcare_user = CommCareUser.create(
            username=format_username('jane', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.other_commcare_user = CommCareUser.create(
            username=format_username('john', cls.domain),
            domain=cls.domain,
            password='***',
        )
        cls.super_user = WebUser.create(
            username='super@woman.com',
            domain=cls.other_domain,
            password='***',
        )
        cls.super_user.is_superuser = True
        cls.super_user.save()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        super(GetRestoreUserTest, cls).tearDownClass()

    def test_get_restore_user_web_user(self):
        self.assertIsInstance(get_restore_user(self.domain, self.web_user, None), OTARestoreWebUser)

    def test_get_restore_user_commcare_user(self):
        self.assertIsInstance(get_restore_user(self.domain, self.commcare_user, None), OTARestoreCommCareUser)

    def test_get_restore_user_as_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.commcare_user
            ),
            OTARestoreCommCareUser,
        )

    def test_get_restore_user_as_web_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.web_user
            ),
            OTARestoreWebUser,
        )

    def test_get_restore_user_as_super_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.super_user
            ),
            OTARestoreWebUser,
        )

    def test_get_restore_user_as_user_for_commcare_user(self):
        user = get_restore_user(
            self.domain,
            self.commcare_user,
            self.other_commcare_user
        )
        self.assertEquals(user.user_id, self.other_commcare_user._id)
