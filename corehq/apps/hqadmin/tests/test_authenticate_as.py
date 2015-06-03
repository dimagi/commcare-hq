from django.test import TestCase, SimpleTestCase
from django.core.urlresolvers import reverse

from corehq.apps.users.models import WebUser, CommCareUser

from ..forms import AuthenticateAsForm
from ..views import AuthenticateAs


class AuthenticateAsFormTest(TestCase):

    def test_valid_data(self):
        mobile_worker = CommCareUser.create('potter', 'harry', '123')

        data = {
            'username': 'harry',
            'domain': 'potter'
        }
        form = AuthenticateAsForm(data)
        self.assertTrue(form.is_valid(), form.errors)

        data = {
            'username': 'harry@potter.commcarehq.org',
        }
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_data(self):
        data = {
            'username': 'harry',
            'domain': 'potter'
        }
        form = AuthenticateAsForm(data)
        self.assertFalse(form.is_valid())

        data = {
            'username': 'harry',
        }
        form = AuthenticateAsForm(data)
        self.assertFalse(form.is_valid())


class AuthenticateAsIntegrationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'my-test-views'
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.domain, cls.username, cls.password, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()

    def test_authenticate_as(self):
        mobile_worker = CommCareUser.create('potter', 'harry', '123')
        self.client.login(username=self.username, password=self.password)

        resp = self.client.get(reverse(AuthenticateAs.urlname))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(type(resp.context['form']), AuthenticateAsForm)

        form = resp.context['form']
        form.data['username'] = 'harry'
        form.data['domain'] = 'potter'

        resp = self.client.post(reverse(AuthenticateAs.urlname), form.data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['user'].username, 'harry')
