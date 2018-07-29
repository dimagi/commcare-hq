from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.tests.test_views import BaseAutocompleteTest
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users


class TestEmailAuthenticationFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        self.verify(True, reverse("login"), "auth-username")

    def test_autocomplete_disabled(self):
        self.verify(False, reverse("login"), "auth-username")


class TestBugReport(TestCase):
    domain = 'test-bug-report'

    @classmethod
    def setUpClass(cls):
        super(TestBugReport, cls).setUpClass()
        delete_all_users()
        cls.project = create_domain(cls.domain)
        cls.web_user = WebUser.create(
            cls.domain,
            'bug-dude',
            password='***',
        )
        cls.web_user.is_superuser = True
        cls.web_user.save()
        cls.commcare_user = CommCareUser.create(
            cls.domain,
            'bug-kid',
            password='***',
        )
        cls.url = reverse("bug_report")

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.project.delete()
        super(TestBugReport, cls).tearDownClass()

    def _default_payload(self, username):
        return {
            'subject': 'Bug',
            'username': username,
            'domain': self.domain,
            'url': 'www.bugs.com',
            'message': 'CommCare is broken, help!',
            'app_id': '',
            'cc': '',
            'email': '',
            '500traceback': '',
        }

    def _post_bug_report(self, payload):
        return self.client.post(
            self.url,
            payload,
            HTTP_USER_AGENT='firefox',
        )

    def test_basic_bug_submit(self):
        self.client.login(username=self.web_user.username, password='***')

        payload = self._default_payload(self.web_user.username)

        response = self._post_bug_report(payload)
        self.assertEqual(response.status_code, 200)

    def test_project_description_web_user(self):
        self.client.login(username=self.web_user.username, password='***')

        payload = self._default_payload(self.web_user.username)
        payload.update({
            'project_description': 'Great NGO, Just Great',
        })

        domain_object = Domain.get_by_name(self.domain)
        self.assertIsNone(domain_object.project_description)

        response = self._post_bug_report(payload)
        self.assertEqual(response.status_code, 200)
        domain_object = Domain.get_by_name(self.domain)
        self.assertEqual(domain_object.project_description, 'Great NGO, Just Great')

        # Don't update if they've made it blank
        payload.update({
            'project_description': '',
        })
        response = self._post_bug_report(payload)
        self.assertEqual(response.status_code, 200)
        domain_object = Domain.get_by_name(self.domain)
        self.assertEqual(domain_object.project_description, 'Great NGO, Just Great')

    def test_project_description_commcare_user(self):
        self.client.login(username=self.commcare_user.username, password='***')

        payload = self._default_payload(self.commcare_user.username)
        payload.update({
            'project_description': 'Great NGO, Just Great',
        })

        domain_object = Domain.get_by_name(self.domain)
        self.assertIsNone(domain_object.project_description)

        response = self._post_bug_report(payload)
        self.assertEqual(response.status_code, 200)
        domain_object = Domain.get_by_name(self.domain)

        # Shouldn't be able to update description as commcare user
        self.assertIsNone(domain_object.project_description)
