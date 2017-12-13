from __future__ import absolute_import
from collections import namedtuple
from django.contrib.auth import get_user_model
from django.test import TestCase
from corehq.apps.users.forms import SetUserPasswordForm

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
