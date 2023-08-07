from collections import namedtuple

from django.contrib.auth import get_user_model
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.forms import SetUserPasswordForm
from corehq.apps.users.models import CommCareUser

Project = namedtuple('Project', ['name', 'strong_mobile_passwords'])


class TestStrongSetUserPasswordForm(TestCase):
    def setUp(self):
        super(TestStrongSetUserPasswordForm, self).setUp()
        self.project = Project('mydomain', True)
        self.user = get_user_model().objects.create_user('tswift')

    def tearDown(self):
        self.user.delete()
        super(TestStrongSetUserPasswordForm, self).tearDown()

    def form(self, password):
        return SetUserPasswordForm(self.project, user_id=self.user.id, user=self.user, data={
            "new_password1": password,
            "new_password2": password,
        })

    def test_weak_password(self):
        form = self.form("Taylor")
        self.assertFalse(form.is_valid())

    def test_strong_password(self):
        form = self.form("TaylorSwift89!")
        self.assertTrue(form.is_valid())


class TestWeakSetUserPasswordForm(TestCase):
    def setUp(self):
        super(TestWeakSetUserPasswordForm, self).setUp()
        self.project = Project('mydomain', False)
        self.user = get_user_model().objects.create_user('tswift')

    def tearDown(self):
        self.user.delete()
        super(TestWeakSetUserPasswordForm, self).tearDown()

    def form(self, password):
        return SetUserPasswordForm(self.project, user_id=self.user.id, user=self.user, data={
            "new_password1": password,
            "new_password2": password,
        })

    def test_weak_password(self):
        form = self.form("Taylor")
        self.assertTrue(form.is_valid())

    def test_strong_password(self):
        form = self.form("TaylorSwift89!")
        self.assertTrue(form.is_valid())


class TestSetMobileUserPasswordForm(TestCase):

    def test_login_attempts_are_cleared_after_reset(self):
        self.mobile_user.login_attempts = 10
        self.mobile_user.save()

        form = self.form("TaylorSwift89!")
        form.full_clean()
        form.save()

        refetched_user = CommCareUser.get_by_username('test-user')
        self.assertEqual(0, refetched_user.login_attempts)

    def form(self, password):
        django_user = self.mobile_user.get_django_user()
        return SetUserPasswordForm(self.domain_obj, user_id=django_user.id, user=django_user, data={
            "new_password1": password,
            "new_password2": password,
        })

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self):
        super().setUp()
        self.mobile_user = CommCareUser.create(self.domain, 'test-user', 'abc123', None, None)
        self.addCleanup(self.mobile_user.delete, self.domain, deleted_by=None)
