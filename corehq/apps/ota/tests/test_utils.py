from django.test import TestCase

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.users.util import format_username
from corehq.apps.domain.models import Domain

from corehq.apps.ota.utils import is_permitted_to_restore, get_restore_user


class RestorePermissionsTest(TestCase):
    domain = 'goats'
    other_domain = 'sheep'

    @classmethod
    def setUpClass(cls):
        super(RestorePermissionsTest, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()

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

    @classmethod
    def tearDownClass(cls):
        super(RestorePermissionsTest, cls).tearDownClass()
        cls.web_user.delete()
        cls.commcare_user.delete()
        cls.super_user.delete()
        cls.project.delete()
        cls.other_project.delete()

    def test_commcare_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            None,
            False,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_wrong_domain(self):
        is_permitted, message = is_permitted_to_restore(
            'wrong-domain',
            self.commcare_user,
            None,
            False,
        )
        self.assertFalse(is_permitted)
        self.assertIsNotNone(message)

    def test_web_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            None,
            False,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            u'{}@{}'.format(self.commcare_user.raw_username, self.domain),
            True,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_user_bad_privelege(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            u'{}@{}'.format(self.commcare_user.raw_username, self.domain),
            False,
        )
        self.assertFalse(is_permitted)
        self.assertIsNotNone(message)

    def test_web_user_as_user_bad_username(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.commcare_user.raw_username,  # Malformed, should include domain
            True,
        )
        self.assertFalse(is_permitted)
        self.assertIsNotNone(message)

    def test_web_user_as_user_bad_domain(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            u'{}@wrong-domain'.format(self.commcare_user.raw_username),
            True,
        )
        self.assertFalse(is_permitted)
        self.assertIsNotNone(message)

    def test_web_user_as_other_web_user(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.web_user.username,
            True,
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
            u'{}@{}'.format(self.commcare_user.raw_username, self.domain),
            False,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)


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
        cls.super_user = WebUser.create(
            username='super@woman.com',
            domain=cls.other_domain,
            password='***',
        )
        cls.super_user.is_superuser = True
        cls.super_user.save()

    @classmethod
    def tearDownClass(cls):
        super(GetRestoreUserTest, cls).tearDownClass()
        cls.web_user.delete()
        cls.commcare_user.delete()
        cls.super_user.delete()
        cls.other_project.delete()
        cls.project.delete()

    def test_get_restore_user_web_user(self):
        self.assertIsNotNone(get_restore_user(self.domain, self.web_user, None))

    def test_get_restore_user_commcare_user(self):
        self.assertIsNotNone(get_restore_user(self.domain, self.commcare_user, None))

    def test_get_restore_user_as_user(self):
        self.assertIsNotNone(
            get_restore_user(
                self.domain,
                self.web_user,
                '{}@{}'.format(self.commcare_user.raw_username, self.domain)
            )
        )

    def test_get_restore_user_as_web_user(self):
        self.assertIsNotNone(
            get_restore_user(
                self.domain,
                self.web_user,
                self.web_user.username,
            )
        )

    def test_get_restore_user_as_super_user(self):
        self.assertIsNotNone(
            get_restore_user(
                self.domain,
                self.web_user,
                self.super_user.username,
            )
        )

    def test_get_restore_user_not_found(self):
        self.assertIsNone(
            get_restore_user(
                self.domain,
                self.web_user,
                '{}@wrong-domain'.format(self.commcare_user.raw_username, self.domain)
            )
        )
