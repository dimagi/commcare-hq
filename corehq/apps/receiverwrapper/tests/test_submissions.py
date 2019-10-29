import json
import os
from io import BytesIO

from django.conf import settings
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.urls import reverse

from mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.util.json import CommCareJSONEncoder
from corehq.util.test_utils import TestFileMixin, softer_assert


class BaseSubmissionTest(TestCase):
    def setUp(self):
        super(BaseSubmissionTest, self).setUp()
        self.domain = create_domain("submit")
        self.couch_user = CommCareUser.create(self.domain.name, "test", "foobar")
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])

        self.use_sql = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)
        FormProcessorTestUtils.delete_all_cases(self.domain.name)
        self.couch_user.delete()
        self.domain.delete()
        super(BaseSubmissionTest, self).tearDown()

    def _submit(self, formname, **extra):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        attachments = extra.pop("attachments", None)
        url = extra.pop('url', self.url)
        with open(file_path, "rb") as f:
            data = {"xml_submission_file": f}
            if attachments:
                data.update(attachments)
            return self.client.post(url, data, **extra)


class SubmissionTest(BaseSubmissionTest):
    maxDiff = None

    def _get_expected_json(self, form_id, xmlns):
        filename = 'expected_form_{}.json'.format(
            'sql' if self.use_sql else 'couch'
        )
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            expected = json.load(f)

        expected['_id'] = form_id
        expected['xmlns'] = str(xmlns)

        return expected

    def _test(self, form, xmlns):
        response = self._submit(form, HTTP_DATE='Mon, 11 Apr 2011 18:24:43 GMT')
        xform_id = response['X-CommCareHQ-FormID']
        foo = FormAccessors(self.domain.name).get_form(xform_id).to_json()
        self.assertTrue(foo['received_on'])

        for key in ['form', 'external_blobs', '_rev', 'received_on', 'user_id', 'server_modified_on']:
            if key in foo:
                del foo[key]

        # normalize the json
        foo = json.loads(json.dumps(foo, cls=CommCareJSONEncoder))
        expected = self._get_expected_json(xform_id, xmlns)
        self.assertEqual(foo, expected)

    def test_submit_simple_form(self):
        self._test(
            form='simple_form.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    def test_submit_bare_form(self):
        self._test(
            form='bare_form.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    def test_submit_user_registration(self):
        self._test(
            form='user_registration.xml',
            xmlns='http://openrosa.org/user/registration',
        )

    def test_submit_with_case(self):
        self._test(
            form='form_with_case.xml',
            xmlns='http://commcarehq.org/test/submit',
        )

    def test_submit_with_namespaced_meta(self):
        self._test(
            form='namespace_in_meta.xml',
            xmlns='http://bihar.commcarehq.org/pregnancy/new',
        )

    @softer_assert()
    def test_submit_deprecated_form(self):
        self._submit('simple_form.xml')
        response = self._submit('simple_form_edited.xml', url=reverse("receiver_secure_post", args=[self.domain]))
        xform_id = response['X-CommCareHQ-FormID']
        form = FormAccessors(self.domain.name).get_form(xform_id)
        self.assertEqual(1, len(form.history))
        self.assertEqual(self.couch_user.get_id, form.history[0].user)


@patch('corehq.apps.receiverwrapper.views.domain_requires_auth', return_value=True)
class NoAuthSubmissionTest(BaseSubmissionTest):
    def setUp(self):
        super(NoAuthSubmissionTest, self).setUp()
        self.url = self.url + '?authtype=noauth'
        # skip any authorization
        self.client = Client()

    def test_successful_processing_for_demo_user_form(self, *_):
        response = self._submit('demo_mode_simple_form.xml', url=self.url)
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Demo user ID form not processed in demo mode')

    def test_ignore_all_non_demo_user_submissions(self, *_):
        response = self._submit('simple_form.xml', url=self.url)
        self.assertEqual(response.status_code, 403)


@patch('corehq.apps.receiverwrapper.views.domain_requires_auth', return_value=True)
class DefaultDemoModeSubmissionTest(BaseSubmissionTest):
    """
        Demo Mode means the request is being sent with param submit_mode=demo and authtype as noauth
        The user id in the form is expected to be DEMO_USER_ID
        Only forms submitted with user ID as demo_user are processed.
    """
    def setUp(self):
        super(DefaultDemoModeSubmissionTest, self).setUp()
        self.domain.secure_submissions = True
        self.domain.save()
        self.url = self.url + '?submit_mode=demo&authtype=noauth'
        # skip any authorization
        self.client = Client()

    def test_successful_processing_for_demo_user_form(self, *_):
        response = self._submit('demo_mode_simple_form.xml', url=self.url)
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Demo user ID form not processed in demo mode')

    def test_ignore_all_non_demo_user_submissions(self, *_):
        response = self._submit('simple_form.xml', url=self.url)
        self.assertFalse('X-CommCareHQ-FormID' in response, 'Non Demo ID form processed in demo mode')


@patch('corehq.apps.receiverwrapper.views.domain_requires_auth', return_value=True)
class PracticeMobileWorkerSubmissionTest(BaseSubmissionTest):
    """
    Just like demo mode, the request is sent with param submit_mode=demo and authtype=noauth
    but the userID in the form is expected to be the user ID of the practice mobile worker
    """
    def setUp(self):
        super(PracticeMobileWorkerSubmissionTest, self).setUp()
        self.url = self.url + '?submit_mode=demo&authtype=noauth'
        # skip any authorization
        self.client = Client()

    @patch('corehq.apps.receiverwrapper.util.IGNORE_ALL_DEMO_USER_SUBMISSIONS', True)
    @patch('corehq.apps.users.models.CommCareUser.get_by_user_id')
    def test_ignore_all_practice_mobile_worker_submissions_in_demo_mode(self, user_stub, *_):
        # ignore submission if from a practice mobile worker and HQ is ignoring all demo user submissions
        self.couch_user.is_demo_user = True
        user_stub.return_value = self.couch_user
        response = self._submit('simple_form.xml', url=self.url)
        self.assertFalse('X-CommCareHQ-FormID' in response, 'Practice mobile worker form processed in demo mode')


class NormalModeSubmissionTest(BaseSubmissionTest):
    """
    In case we are ignoring all demo user form submissions, the form is ignored if submitted by a demo user
    Else process all forms.
    """
    def test_form_with_demo_user_id_in_normal_mode(self):
        response = self._submit('demo_mode_simple_form.xml')
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Demo user ID form not processed in normal mode')

    def test_form_with_non_demo_user_id_in_normal_mode(self):
        response = self._submit('simple_form.xml')
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Non Demo user ID form not processed in normal mode')

    @patch('corehq.apps.receiverwrapper.util.IGNORE_ALL_DEMO_USER_SUBMISSIONS', True)
    @patch('corehq.apps.users.models.CommCareUser.get_by_user_id')
    def test_ignore_all_practice_mobile_worker_submissions_in_normal_mode(self, user_stub, *_):
        user_stub.return_value = self.couch_user
        response = self._submit('simple_form.xml')
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Normal user form not processed in non-demo mode')

        self.couch_user.is_demo_user = True
        response = self._submit('simple_form.xml')
        self.assertFalse('X-CommCareHQ-FormID' in response,
                         'Practice mobile worker form processed in non-demo mode')

    @patch('corehq.apps.receiverwrapper.util.IGNORE_ALL_DEMO_USER_SUBMISSIONS', True)
    def test_invalid_form_xml(self, *_):
        response = self._submit('invalid_form_xml.xml')
        self.assertTrue(response.status_code, 422)
        self.assertTrue("There was an error processing the form: Invalid XML" in response.content.decode('utf-8'))


@use_sql_backend
class SubmissionTestSQL(SubmissionTest):

    @softer_assert()
    def test_submit_deprecated_form_with_attachments(self):
        def list_attachments(form):
            return sorted(
                (att.name, att.open().read())
                for att in form.get_attachments()
                if att.name != "form.xml"
            )

        self._submit('simple_form.xml', attachments={
            "image": BytesIO(b"fake image"),
            "file": BytesIO(b"text file"),
        })
        response = self._submit(
            'simple_form_edited.xml',
            attachments={"image": BytesIO(b"other fake image")},
            url=reverse("receiver_secure_post", args=[self.domain]),
        )
        acc = FormAccessors(self.domain.name)
        new_form = acc.get_form(response['X-CommCareHQ-FormID'])
        old_form = acc.get_form(new_form.deprecated_form_id)
        self.assertIn(b"<bop>bang</bop>", old_form.get_xml())
        self.assertIn(b"<bop>bong</bop>", new_form.get_xml())
        self.assertEqual(list_attachments(old_form),
            [("file", b"text file"), ("image", b"fake image")])
        self.assertEqual(list_attachments(new_form),
            [("file", b"text file"), ("image", b"other fake image")])


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class SubmissionSQLTransactionsTest(TestCase, TestFileMixin):
    root = os.path.dirname(__file__)
    file_path = ('data',)
    domain = 'test-domain'

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        FormProcessorTestUtils.delete_all_ledgers(self.domain)
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super(SubmissionSQLTransactionsTest, self).tearDown()

    def test_case_ledger_form(self):
        form_xml = self.get_xml('case_ledger_form')
        result = submit_form_locally(form_xml, domain=self.domain)

        # use tuple unpacking to verify single closed case
        closed_case, = [case for case in result.cases if case.closed]
        transaction = closed_case.get_transaction_by_form_id(result.xform.form_id)
        self.assertTrue(transaction.is_form_transaction)
        self.assertTrue(transaction.is_case_create)
        self.assertTrue(transaction.is_case_close)
        self.assertTrue(transaction.is_ledger_transaction)

        form_xml = self.get_xml('case_ledger_form_2')
        result = submit_form_locally(form_xml, domain=self.domain)

        transaction = result.cases[0].get_transaction_by_form_id(result.xform.form_id)
        self.assertTrue(transaction.is_form_transaction)
