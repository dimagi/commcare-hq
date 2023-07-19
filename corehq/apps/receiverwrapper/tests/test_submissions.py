import json
import os
from io import BytesIO
from rest_framework import status
import copy

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.urls import reverse
from django.conf import settings

from unittest.mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.json import CommCareJSONEncoder
from corehq.util.test_utils import TestFileMixin, softer_assert

from couchforms.exceptions import (
    InvalidAttachmentFileError,
    InvalidSubmissionFileExtensionError
)


class BaseSubmissionTest(TestCase):
    def setUp(self):
        super(BaseSubmissionTest, self).setUp()
        self.domain = create_domain("submit")
        self.couch_user = CommCareUser.create(self.domain.name, "test", "foobar", None, None)
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)
        FormProcessorTestUtils.delete_all_cases(self.domain.name)
        self.couch_user.delete(self.domain.name, deleted_by=None)
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


@sharded
class SubmissionTest(BaseSubmissionTest):
    maxDiff = None

    def _get_expected_json(self, form_id, xmlns):
        filename = 'expected_form_sql.json'
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            expected = json.load(f)

        expected['_id'] = form_id
        expected['xmlns'] = str(xmlns)

        return expected

    def _test(self, form, xmlns):
        response = self._submit(form, HTTP_DATE='Mon, 11 Apr 2011 18:24:43 GMT')
        xform_id = response['X-CommCareHQ-FormID']
        foo = XFormInstance.objects.get_form(xform_id, self.domain.name).to_json()
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

    def test_submit_with_non_bmp_chars(self):
        self._test(
            form="form_data_with_non_bmp_chars.xml",
            xmlns='http://commcarehq.org/test/submit',
        )
        case_id = 'ad38211be256653bceac8e2156475667'
        case = CommCareCase.objects.get_case(case_id, self.domain.name)
        self.assertEqual(case.name, "👕 👖 👔 👗 👙")

    @softer_assert()
    def test_submit_deprecated_form(self):
        self._submit('simple_form.xml')  # submit a form to try again as duplicate
        response = self._submit('simple_form_edited.xml', url=reverse("receiver_secure_post", args=[self.domain]))
        xform_id = response['X-CommCareHQ-FormID']
        form = XFormInstance.objects.get_form(xform_id, self.domain.name)
        self.assertEqual(1, len(form.history))
        self.assertEqual(self.couch_user.get_id, form.history[0].user)

    def test_invalid_form_submission_file_extension(self):
        response = self._submit('suspicious_form.abc', url=reverse("receiver_secure_post", args=[self.domain]))
        expected_error = InvalidSubmissionFileExtensionError()
        self.assertEqual(response.status_code, expected_error.status_code)
        self.assertEqual(
            response.content.decode('utf-8'),
            f'<OpenRosaResponse xmlns="http://openrosa.org/http/response"><message nature="processing_failure">'
            f'{expected_error.message}'
            f'</message></OpenRosaResponse>'
        )

    def test_submission_with_only_mobile_supported_content_types(self):
        image = SimpleUploadedFile("image.abc", b"fake image", content_type="application/octet-stream")
        response = self._submit('simple_form.xml', attachments={
            "image.png": image,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_submission_with_only_formplayer_supported_content_types(self):
        image = SimpleUploadedFile("image.abc", b"fake image", content_type="application/pdf")
        response = self._submit('simple_form.xml', attachments={
            "image.png": image,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_valid_attachment_file_extension_with_valid_mimetype(self):
        image = SimpleUploadedFile("image.png", b"fake image", content_type="image/png")
        response = self._submit('simple_form.xml', attachments={
            "image.png": image,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_attachment_file_extension_with_valid_mimetype(self):
        image = SimpleUploadedFile("image.xyz", b"fake image", content_type="image/png")
        response = self._submit('simple_form.xml', attachments={
            "image.xyz": image,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_valid_attachment_file_extension_with_invalid_mimetype(self):
        image = SimpleUploadedFile("image.png", b"fake image", content_type="fake/image")
        response = self._submit('simple_form.xml', attachments={
            "image.png": image,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_attachment_file_extension_with_invalid_mimetype(self):
        image = SimpleUploadedFile("image.xyz", b"fake image", content_type="fake/image")
        response = self._submit('simple_form.xml', attachments={
            "image.xyz": image,
        })
        expected_error = InvalidAttachmentFileError()
        self.assertEqual(response.status_code, expected_error.status_code)
        self.assertEqual(
            response.content.decode('utf-8'),
            f'<OpenRosaResponse xmlns="http://openrosa.org/http/response"><message nature="processing_failure">'
            f'{expected_error.message}'
            f'</message></OpenRosaResponse>'
        )

    @softer_assert()
    def test_submit_deprecated_form_with_attachments(self):
        def list_attachments(form):
            return sorted(
                (att.name, att.open().read())
                for att in form.get_attachments()
                if att.name != "form.xml"
            )

        # submit a form to try again as duplicate with one attachment modified
        self._submit('simple_form.xml', attachments={
            "image": BytesIO(b"fake image"),
            "audio": BytesIO(b"fake audio"),
        })
        response = self._submit(
            'simple_form_edited.xml',
            attachments={"image": BytesIO(b"other fake image")},
            url=reverse("receiver_secure_post", args=[self.domain]),
        )
        new_form = XFormInstance.objects.get_form(response['X-CommCareHQ-FormID'])
        old_form = XFormInstance.objects.get_form(new_form.deprecated_form_id)
        self.assertIn(b"<bop>bang</bop>", old_form.get_xml())
        self.assertIn(b"<bop>bong</bop>", new_form.get_xml())
        self.assertEqual(
            list_attachments(old_form),
            [("audio", b"fake audio"), ("image", b"fake image")])
        self.assertEqual(
            list_attachments(new_form),
            [("audio", b"fake audio"), ("image", b"other fake image")])

    def test_submit_invalid_attachment_size(self):
        file_data = BytesIO(b"a" * (settings.MAX_UPLOAD_SIZE_ATTACHMENT + 1))
        response = self._submit(
            'simple_form.xml',
            attachments={"file": file_data},
            url=reverse("receiver_secure_post", args=[self.domain]),
        )
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(response.content.decode('utf-8'),
                         f"Attachment exceeds {settings.MAX_UPLOAD_SIZE_ATTACHMENT/(1024*1024):,.0f}MB"
                         f" size limit\n")

    def test_submit_valid_attachment_size_multiple(self):
        file_data = BytesIO(b"a" * (settings.MAX_UPLOAD_SIZE_ATTACHMENT - 1))
        response = self._submit(
            'simple_form.xml',
            attachments={"file": file_data, "image": copy.copy(file_data)},
            url=reverse("receiver_secure_post", args=[self.domain]),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        form = XFormInstance.objects.get_form(response['X-CommCareHQ-FormID'])
        self.assertEqual(len(form.get_attachments()), 3)


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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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

    @override_settings(IGNORE_ALL_DEMO_USER_SUBMISSIONS=True)
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

    @override_settings(IGNORE_ALL_DEMO_USER_SUBMISSIONS=True)
    @patch('corehq.apps.users.models.CommCareUser.get_by_user_id')
    @softer_assert()
    def test_ignore_all_practice_mobile_worker_submissions_in_normal_mode(self, user_stub):
        user_stub.return_value = self.couch_user
        response = self._submit('simple_form.xml')
        self.assertTrue('X-CommCareHQ-FormID' in response, 'Normal user form not processed in non-demo mode')

        self.couch_user.is_demo_user = True
        response = self._submit('simple_form.xml')
        self.assertFalse('X-CommCareHQ-FormID' in response,
                         'Practice mobile worker form processed in non-demo mode')

    @override_settings(IGNORE_ALL_DEMO_USER_SUBMISSIONS=True)
    def test_invalid_form_xml(self):
        response = self._submit('invalid_form_xml.xml')
        self.assertTrue(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertTrue("There was an error processing the form: Invalid XML" in response.content.decode('utf-8'))

    @override_settings(IGNORE_ALL_DEMO_USER_SUBMISSIONS=True)
    @patch('corehq.apps.receiverwrapper.util._notify_ignored_form_submission')
    @patch('corehq.apps.users.models.CommCareUser.get_by_user_id')
    def test_notification(self, user_stub, notification):
        user_stub.return_value = self.couch_user
        self.couch_user.is_demo_user = True

        response = self._submit('simple_form_before_2.44.0.xml')
        self.assertFalse('X-CommCareHQ-FormID' in response,
                         'Practice mobile worker form processed in non-demo mode')
        self.assertFalse(notification.called)

        response = self._submit('simple_form.xml')
        self.assertFalse('X-CommCareHQ-FormID' in response,
                         'Practice mobile worker form processed in non-demo mode')
        self.assertTrue(notification.called)


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


@patch('corehq.apps.receiverwrapper.rate_limiter.SHOULD_RATE_LIMIT_SUBMISSIONS', True)
@patch('corehq.apps.receiverwrapper.rate_limiter.global_submission_rate_limiter.allow_usage', return_value=True)
class SubmitFormLocallyRateLimitTest(TestCase, TestFileMixin):
    root = os.path.dirname(__file__)
    file_path = ('data',)
    domain = 'test-domain'

    def test_rate_limiting(self, allow_usage):
        form_xml = self.get_xml('simple_form')
        submit_form_locally(form_xml, domain=self.domain)
        allow_usage.assert_called()

    def test_no_rate_limiting(self, allow_usage):
        form_xml = self.get_xml('simple_form')
        submit_form_locally(form_xml, domain=self.domain, max_wait=None)
        allow_usage.assert_not_called()
