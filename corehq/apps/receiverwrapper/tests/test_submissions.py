import json

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
import os

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import run_with_all_backends


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

        self.use_sql = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False)

    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()

    def _submit(self, formname, **extra):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            return self.client.post(self.url, {
                "xml_submission_file": f
            }, **extra)

    def _get_expected_json(self, form_id, xmlns):
        filename = 'expected_form_{}.json'.format(
            'sql' if self.use_sql else 'couch'
        )
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            expected = json.load(f)

        if '_id' in expected:
            expected['_id'] = form_id
        else:
            expected['form_id'] = unicode(form_id)
        expected['xmlns'] = unicode(xmlns)

        return expected

    def _test(self, form, xmlns):
        response = self._submit(form, HTTP_DATE='Mon, 11 Apr 2011 18:24:43 GMT')
        xform_id = response['X-CommCareHQ-FormID']
        foo = FormAccessors(self.domain.name).get_form(xform_id).to_json()
        self.assertTrue(foo['received_on'])

        if not self.use_sql:
            n_times_saved = int(foo['_rev'].split('-')[0])
            self.assertEqual(n_times_saved, 1)

        for key in ['form', '_attachments', '_rev', 'received_on', 'user_id']:
            if key in foo:
                del foo[key]

        # normalize the json
        foo = json.loads(json.dumps(foo))
        expected = self._get_expected_json(xform_id, xmlns)
        self.assertEqual(foo, expected)

    @run_with_all_backends
    def test_submit_simple_form(self):
        self._test(
            form='simple_form.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    @run_with_all_backends
    def test_submit_bare_form(self):
        self._test(
            form='bare_form.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    @run_with_all_backends
    def test_submit_user_registration(self):
        self._test(
            form='user_registration.xml',
            xmlns='http://openrosa.org/user/registration',
        )

    @run_with_all_backends
    def test_submit_with_case(self):
        self._test(
            form='form_with_case.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    @run_with_all_backends
    def test_submit_with_namespaced_meta(self):
        self._test(
            form='namespace_in_meta.xml',
            xmlns='http://bihar.commcarehq.org/pregnancy/new',
        )
