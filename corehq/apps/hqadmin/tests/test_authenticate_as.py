from django.test import TestCase
from django.core.urlresolvers import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, CommCareUser

from ..forms import AuthenticateAsForm
from ..views import AuthenticateAs


class AuthenticateAsFormTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mobile_worker = CommCareUser.create('potter', 'harry@potter.commcarehq.org', '123')
        cls.regular = WebUser.create('pottery', 'awebuser', '***', is_active=True)

    @classmethod
    def tearDownClass(cls):
        cls.mobile_worker.delete()
        cls.regular.delete()

    def test_valid_data(self):
        data = {
            'username': 'harry',
            'domain': 'potter'
        }
        form = AuthenticateAsForm(data)
        self.assertTrue(form.is_valid(), form.errors)

        data = {
            'username': 'harry@potter.commcarehq.org',
        }
        form = AuthenticateAsForm(data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_data(self):
        data = {
            'username': 'ron-weasley',
            'domain': 'potter'
        }
        form = AuthenticateAsForm(data)
        self.assertFalse(form.is_valid())

        data = {
            'username': 'ron-weasley',
        }
        form = AuthenticateAsForm(data)
        self.assertFalse(form.is_valid())

    def test_no_login_as_other_webuser(self):
        data = {
            'username': 'awebuser'
        }
        form = AuthenticateAsForm(data)
        self.assertFalse(form.is_valid())
        self.assertTrue('not a CommCareUser' in str(form.errors))


class AuthenticateAsIntegrationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='my-test-views')
        cls.domain.save()
        cls.username = 'cornelius'
        cls.regular_name = 'ron'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, is_active=True)

        cls.user.is_superuser = True
        cls.user.save()
        cls.mobile_worker = CommCareUser.create('potter', 'harry@potter.commcarehq.org', '123')
        cls.regular = WebUser.create(cls.domain.name, cls.regular_name, cls.password, is_active=True)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.mobile_worker.delete()
        cls.regular.delete()
        cls.domain.delete()

    def test_authenticate_as(self):
        self.client.login(username=self.username, password=self.password)

        resp = self.client.get(reverse(AuthenticateAs.urlname))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(type(resp.context['form']), AuthenticateAsForm)

        form = resp.context['form']
        form.data['username'] = 'harry'
        form.data['domain'] = 'potter'

        resp = self.client.post(reverse(AuthenticateAs.urlname), form.data, follow=True)
        self.assertEqual(
            self.client.session['_auth_user_id'],
            self.mobile_worker.get_django_user().id
        )

    def test_permisssions_for_authenticate_as(self):
        self.client.login(username=self.regular_name, password=self.password)

        resp = self.client.get(reverse(AuthenticateAs.urlname))
        self.assertTrue('no_permissions' in resp.url)

        resp = self.client.post(reverse(AuthenticateAs.urlname), {})
        self.assertTrue('no_permissions' in resp.url)
        self.assertEqual(
            self.client.session['_auth_user_id'],
            self.regular.get_django_user().id
        )
