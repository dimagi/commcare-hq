from datetime import datetime

from django.contrib.messages import get_messages
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
from django.utils.html import escape

from corehq.apps.accounting.models import DefaultProductPlan
from corehq.apps.domain.models import Domain
from corehq.apps.registration.models import (
    RegistrationRequest,
    SelfSignupWorkflow,
)
from corehq.apps.users.models import WebUser


class TestConfirmDomainView(TestCase):

    def setUp(self):
        super().setUp()
        self.domain = Domain(name='the-name-of-a-domain', is_active=False)
        self.domain.save()
        self.addCleanup(self.domain.delete)

        self.user = WebUser.create(self.domain.name, 'test-user', 'password', None, None, 'testy@example.com')
        self.addCleanup(self.user.delete, self.domain.name, deleted_by=None)

        self.client = Client()
        self.client.force_login(self.user.get_django_user())
        self.client.defaults.update({'plan': DefaultProductPlan.get_default_plan_version()})

    def tearDown(self):
        SelfSignupWorkflow.get_in_progress_for_domain.clear(SelfSignupWorkflow, self.domain.name)
        super().tearDown()

    def create_registration_request(self, guid):
        reg_request = RegistrationRequest.objects.create(
            request_time=datetime.now(),
            activation_guid=guid,
            domain=self.domain.name,
            new_user_username=self.user.username
        )
        self.addCleanup(reg_request.delete)

    @staticmethod
    def url(guid=None):
        url = reverse('registration_confirm_domain')
        if guid:
            url += f'{guid}/'
        return url

    def test_confirm_domain(self):
        guid = 'abc123'
        self.create_registration_request(guid)

        response = self.client.get(self.url(guid))
        self.assertRedirects(response, reverse('dashboard_domain', args=[self.domain.name]))

        domain = Domain.get_by_name(self.domain.name)
        self.assertTrue(domain.is_active)

    def test_no_guid(self):
        response = self.client.get(self.url())
        self.assertTemplateUsed(response, 'registration/confirmation_error.html')

        expected_message = 'An account activation key was not provided.'
        self.assertIn(expected_message, response.content.decode())

    def test_bad_guid(self):
        bad_guid = 'bad456'
        response = self.client.get(self.url(bad_guid))
        self.assertTemplateUsed(response, 'registration/confirmation_error.html')

        expected_message = escape(f'The account activation key "{bad_guid}" provided is invalid.')
        self.assertIn(expected_message, response.content.decode())

    def test_domain_already_confirmed(self):
        guid = 'abc123'
        self.create_registration_request(guid)
        self.client.get(self.url(guid))

        response = self.client.get(self.url(guid))
        self.assertRedirects(response, reverse('dashboard_domain', args=[self.domain.name]))

        messages = list(get_messages(response.wsgi_request))
        self.assertIn(
            f'Your account {self.user.username} has already been activated',
            messages[1].message
        )

    def test_self_signup_redirect(self):
        guid = 'abc123'
        self.create_registration_request(guid)
        SelfSignupWorkflow.objects.create(domain=self.domain.name, initiating_user=self.user.username)

        response = self.client.get(self.url(guid))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.get('Location'), reverse('domain_select_plan', args=[self.domain.name]))
