from django.test import TestCase
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm


class PasswordLockoutTest(TestCase):

    def setUp(self):
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.username = 'auser@qwerty.commcarehq.org'
        self.password = 'apassword'
        self.user = WebUser.create(self.domain.name, self.username, self.password)

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_login_lockout(self):
        form = EmailAuthenticationForm(data={'username': self.username, 'password': self.password})
        self.assertEqual(form.is_valid(), True)

        # attempt with bad credentials 5 times to lock out
        for i in range(5):
            form2 = EmailAuthenticationForm(data={'username': self.username, 'password': '***'})
            form2.is_valid()

        form3 = EmailAuthenticationForm(data={'username': self.username, 'password': self.password})
        self.assertEqual(form3.is_valid(), False)
