from django.conf import settings
from django.test import TestCase
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
import os


class SubmissionTest(TestCase):
    def setUp(self):
        # bit of a hack, but the tests optimize around this flag to run faster
        # so when we actually want to test this functionality we need to set
        # the flag to False explicitly
        settings.UNIT_TESTING = False
        self.domain = create_domain("submit")
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain.name, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])

    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()

    def _submit(self, formname):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            return self.client.post(self.url, {
                "xml_submission_file": f
            })

    def _check_for_message(self, excerpt, response, msg=None):
        return self.assertIn(excerpt, str(response), msg)

    def test_submit_simple_form(self):
        self._check_for_message(
            "Thanks for submitting!",
            self._submit("simple_form.xml"),
        )

    def test_submit_bare_form(self):
        self._check_for_message(
            "Thanks for submitting!",
            self._submit("bare_form.xml"),
            "Bare form successfully parsed",
        )

    def test_submit_user_registration(self):
        self._check_for_message(
            "Thanks for registering! Your username is mealz@",
            self._submit("user_registration.xml"),
            "User registration form successfully parsed",
        )

    def test_submit_with_case(self):
        self._check_for_message(
            "Thanks for submitting!",
            self._submit("form_with_case.xml"),
            "Form with case successfully parsed",
        )

    def test_submit_with_namespaced_meta(self):
        self._check_for_message(
            "Thanks for submitting!",
            self._submit("namespace_in_meta.xml"),
            "Form with namespace in meta successfully parsed",
        )
