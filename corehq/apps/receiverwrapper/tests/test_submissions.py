from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
import os
from couchforms.models import XFormInstance


# bit of a hack, but the tests optimize around this flag to run faster
# so when we actually want to test this functionality we need to set
# the flag to False explicitly
@override_settings(UNIT_TESTING=False)
class SubmissionTest(TestCase):
    maxDiff = None

    def setUp(self):
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

    def _submit(self, formname, **extra):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            return self.client.post(self.url, {
                "xml_submission_file": f
            }, **extra)

    def _test(self, form, response_contains, xmlns, msg=None):

        response = self._submit(form,
                                HTTP_DATE='Mon, 11 Apr 2011 18:24:43 GMT')
        xform_id = response['X-CommCareHQ-FormID']
        foo = XFormInstance.get(xform_id).to_json()
        n_times_saved = int(foo['_rev'].split('-')[0])
        self.assertTrue(foo['received_on'])
        for key in ['form', '_attachments', '_rev', 'received_on']:
            del foo[key]
        self.assertEqual(n_times_saved, 1)
        self.assertEqual(foo, {
            "#export_tag": [
                "domain",
                "xmlns"
            ],
            "_id": xform_id,
            "app_id": None,
            "auth_context": {
                "authenticated": False,
                "doc_type": "AuthContext",
                "domain": "submit",
                "user_id": None
            },
            "build_id": None,
            "computed_": {},
            "computed_modified_on_": None,
            "date_header": '2011-04-11T18:24:43Z',
            "doc_type": "XFormInstance",
            "domain": "submit",
            "history": [],
            "initial_processing_complete": True,
            "last_sync_token": None,
            "openrosa_headers": {
                "HTTP_DATE": "Mon, 11 Apr 2011 18:24:43 GMT",
            },
            "partial_submission": False,
            "path": "/a/submit/receiver",
            "submit_ip": "127.0.0.1",
            "xmlns": xmlns
        })
        self.assertIn(response_contains, str(response), msg)

    def test_submit_simple_form(self):
        self._test(
            form='simple_form.xml',
            response_contains="Thanks for submitting!",
            xmlns='http://commcarehq.org/test/submit',
        )

    def test_submit_bare_form(self):
        self._test(
            form='bare_form.xml',
            response_contains="Thanks for submitting!",
            xmlns='http://commcarehq.org/test/submit',
            msg="Bare form successfully parsed",
        )

    def test_submit_user_registration(self):
        self._test(
            form='user_registration.xml',
            response_contains="Thanks for registering! "
                              "Your username is mealz@",
            xmlns='http://openrosa.org/user/registration',
            msg="User registration form successfully parsed",
        )

    def test_submit_with_case(self):
        self._test(
            form='form_with_case.xml',
            response_contains="Thanks for submitting!",
            xmlns='http://commcarehq.org/test/submit',
            msg="Form with case successfully parsed",
        )

    def test_submit_with_namespaced_meta(self):
        self._test(
            form='namespace_in_meta.xml',
            response_contains="Thanks for submitting!",
            xmlns='http://bihar.commcarehq.org/pregnancy/new',
            msg="Form with namespace in meta successfully parsed",
        )
