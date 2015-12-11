from django.core.urlresolvers import reverse
from django.test import TestCase, Client

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class TestHQCsrfMiddleware(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name="delhi", is_active=True)
        cls.domain.save()

        cls.username = 'bombme'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, is_admin=True)
        cls.user.eula.signed = True

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()

    def test_csrf_ON(self):
        with self.settings(CSRF_ALWAYS_OFF=False):
            csrf_sent, csrf_missing = self._form_post_with_and_without_csrf()
            self.assertEqual(csrf_sent, 200)
            self.assertEqual(csrf_missing, 403)

    def test_csrf_OFF(self):
        with self.settings(CSRF_ALWAYS_OFF=True):
            csrf_sent, csrf_missing = self._form_post_with_and_without_csrf()
            self.assertEqual(csrf_sent, 200)
            self.assertEqual(csrf_missing, 200)

    def _form_post_with_and_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        login_page = client.get(reverse('login'))
        csrf_token = login_page.cookies.get('csrftoken')
        client.login(username=self.username, password=self.password)

        form_data = {
            'recipients': '+9199902334',
            'message': 'sms',
            'send_sms_button': ''
        }
        csrf_missing = client.post(reverse('send_to_recipients', args=[self.domain.name]), form_data).status_code

        form_data['csrfmiddlewaretoken'] = csrf_token.value
        csrf_sent = client.post(
            reverse('send_to_recipients', args=[self.domain.name]), form_data, follow=True
        ).status_code

        return csrf_sent, csrf_missing
