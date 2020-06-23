import contextlib
import logging
import os
import tempfile

from django.db.utils import InternalError
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from botocore.exceptions import ConnectionClosedError
from mock import patch

from casexml.apps.case.exceptions import IllegalCaseId
from couchforms.models import UnfinishedSubmissionStub
from couchforms.openrosa_response import ResponseNature
from couchforms.signals import successful_form_received

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.blobs import get_blob_db
from corehq.const import OPENROSA_VERSION_2, OPENROSA_VERSION_3
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.middleware import OPENROSA_VERSION_HEADER
from corehq.util.test_utils import TestFileMixin, flag_enabled, capture_log_output

FORM_WITH_CASE_ID = 'ad38211be256653bceac8e2156475666'


def tmpfile(mode='w', *args, **kwargs):
    fd, path = tempfile.mkstemp(*args, **kwargs)
    return (os.fdopen(fd, mode), path)


class SubmissionErrorTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(SubmissionErrorTest, cls).setUpClass()
        cls.domain = create_domain("submit-errors")
        cls.couch_user = WebUser.create(None, "test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain.name, is_admin=True)
        cls.couch_user.save()
        cls.client = Client()
        cls.client.login(**{'username': 'test', 'password': 'foobar'})
        cls.url = reverse("receiver_post", args=[cls.domain])

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.domain.delete()
        super(SubmissionErrorTest, cls).tearDownClass()

    def setUp(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain.name)
        UnfinishedSubmissionStub.objects.all().delete()

    def _submit(self, formname, open_rosa_header=None):
        open_rosa_header = open_rosa_header or OPENROSA_VERSION_2
        file_path = self.get_path(formname, '')
        with open(file_path, "rb") as f:
            res = self.client.post(
                self.url,
                {"xml_submission_file": f},
                ** {OPENROSA_VERSION_HEADER: open_rosa_header}
            )
            return file_path, res

    def testSubmitBadAttachmentType(self):
        res = self.client.post(self.url, {
                "xml_submission_file": "this isn't a file"
        })
        self.assertEqual(400, res.status_code)
        #self.assertIn("xml_submission_file", res.content)

    def testSubmitDuplicate(self):
        file, res = self._submit('simple_form.xml')
        self.assertEqual(201, res.status_code)
        self.assertIn("   √   ".encode('utf-8'), res.content)

        file, res = self._submit('simple_form.xml')
        self.assertEqual(201, res.status_code)

        _, res_openrosa3 = self._submit('simple_form.xml', open_rosa_header=OPENROSA_VERSION_3)
        self.assertEqual(201, res_openrosa3.status_code)

        self.assertIn("Form is a duplicate", res.content.decode('utf-8'))

        # make sure we logged it
        [log] = FormAccessors(self.domain.name).get_forms_by_type('XFormDuplicate', limit=1)

        self.assertIsNotNone(log)
        self.assertIn("Form is a duplicate", log.problem)
        with open(file, 'rb') as f:
            self.assertEqual(f.read(), log.get_xml())

    def _test_submission_error_post_save(self, openrosa_version):
        evil_laugh = "mwa ha ha!"
        with failing_signal_handler(evil_laugh):
            file, res = self._submit("simple_form.xml", openrosa_version)
            if openrosa_version == OPENROSA_VERSION_3:
                self.assertEqual(422, res.status_code)
                self.assertIn(ResponseNature.POST_PROCESSING_FAILURE.encode('utf-8'), res.content)
            else:
                self.assertEqual(201, res.status_code)
                self.assertIn(ResponseNature.SUBMIT_SUCCESS.encode('utf-8'), res.content)

            form_id = 'ad38211be256653bceac8e2156475664'
            form = FormAccessors(self.domain.name).get_form(form_id)
            self.assertTrue(form.is_normal)
            self.assertTrue(form.initial_processing_complete)
            stubs = UnfinishedSubmissionStub.objects.filter(
                domain=self.domain, xform_id=form_id, saved=True
            ).all()
            self.assertEqual(1, len(stubs))

    def test_submission_error_post_save_2_0(self):
        self._test_submission_error_post_save(OPENROSA_VERSION_2)

    def test_submission_error_post_save_3_0(self):
        self._test_submission_error_post_save(OPENROSA_VERSION_3)
        # make sure that a re-submission has the same response
        self._test_submission_error_post_save(OPENROSA_VERSION_3)

    def _test_submit_bad_data(self, bad_data):
        f, path = tmpfile(mode='wb')
        with f:
            f.write(bad_data)
        with open(path, 'rb') as f:
            with capture_log_output('', logging.WARNING) as logs:
                res = self.client.post(self.url, {
                    "xml_submission_file": f
                })
            self.assertEqual(422, res.status_code)
            self.assertIn('Invalid XML', res.content.decode('utf-8'))

        # make sure we logged it
        [log] = FormAccessors(self.domain.name).get_forms_by_type('SubmissionErrorLog', limit=1)

        self.assertIsNotNone(log)
        self.assertIn('Invalid XML', log.problem)
        self.assertEqual(bad_data, log.get_xml())
        self.assertEqual(log.form_data, {})
        return logs.get_output()

    def test_submit_bad_xml(self):
        log_output = self._test_submit_bad_data(b'\xad\xac\xab\xd36\xe1\xab\xd6\x9dR\x9b')
        self.assertRegexpMatches(log_output, r"Problem receiving submission.*")

    def test_submit_bad_device_log(self):
        log_output = self._test_submit_bad_data(
            "malformed xml dvice log</log></log_subreport></device_report>".encode('utf8')
        )
        self.assertRegexpMatches(log_output, r"Badly formed device log.*")

    def test_missing_xmlns(self):
        file, res = self._submit('missing_xmlns.xml')
        self.assertEqual(422, res.status_code)
        message = "Form is missing a required field: XMLNS"
        self.assertIn(message, res.content.decode('utf-8'))

        # make sure we logged it
        [log] = FormAccessors(self.domain.name).get_forms_by_type('SubmissionErrorLog', limit=1)

        self.assertIsNotNone(log)
        self.assertIn(message, log.problem)
        with open(file, 'rb') as f:
            self.assertEqual(f.read(), log.get_xml())

    @flag_enabled('DATA_MIGRATION')
    def test_data_migration(self):
        file, res = self._submit('simple_form.xml')
        self.assertEqual(503, res.status_code)
        message = "Service Temporarily Unavailable"
        self.assertIn(message, res.content.decode('utf-8'))

    def test_error_saving_normal_form(self):
        sql_patch = patch(
            'corehq.form_processor.backends.sql.processor.FormProcessorSQL.save_processed_models',
            side_effect=InternalError
        )
        couch_patch = patch(
            'corehq.form_processor.backends.couch.processor.FormProcessorCouch.save_processed_models',
            side_effect=InternalError
        )
        with sql_patch, couch_patch:
            with self.assertRaises(InternalError):
                _, res = self._submit('form_with_case.xml')

        stubs = UnfinishedSubmissionStub.objects.filter(
            domain=self.domain, saved=False, xform_id=FORM_WITH_CASE_ID
        ).all()
        self.assertEqual(1, len(stubs))

        form = FormAccessors(self.domain).get_form(FORM_WITH_CASE_ID)
        self.assertTrue(form.is_error)
        self.assertTrue(form.initial_processing_complete)

    def _test_case_processing_error(self, openrosa_version):
        with patch('casexml.apps.case.xform._get_or_update_cases', side_effect=IllegalCaseId):
            _, res = self._submit('form_with_case.xml', open_rosa_header=openrosa_version)

        if openrosa_version == OPENROSA_VERSION_3:
            self.assertEqual(422, res.status_code)
            self.assertIn(ResponseNature.PROCESSING_FAILURE, res.content.decode('utf-8'))
        else:
            self.assertEqual(201, res.status_code)
            self.assertIn(ResponseNature.SUBMIT_ERROR, res.content.decode('utf-8'))

        form = FormAccessors(self.domain).get_form(FORM_WITH_CASE_ID)
        self.assertTrue(form.is_error)
        self.assertFalse(form.initial_processing_complete)

    def test_case_processing_error_2_0(self):
        self._test_case_processing_error(OPENROSA_VERSION_2)

    def test_case_processing_error_3_0(self):
        self._test_case_processing_error(OPENROSA_VERSION_3)
        # make sure that a re-submission has the same response
        self._test_case_processing_error(OPENROSA_VERSION_3)

    def test_no_form_lock_on_submit_device_log(self):
        from corehq.form_processor.submission_post import FormProcessingResult as FPR
        from corehq.form_processor.parsers.form import FormProcessingResult

        class FakeResponse(dict):
            content = "device-log-response"
            status_code = 200
            streaming = False
            cookies = []
            _closable_objects = []

            def has_header(self, name):
                return False

            def set_cookie(self, *args, **kw):
                pass

            def close(self):
                pass

        def process_device_log(self_, xform):
            result = FormProcessingResult(xform)
            # verify form is not locked: acquire lock without XFormLockError
            with result.get_locked_forms() as forms:
                self.assertEqual(forms, [xform])
            calls.append(1)
            return FPR(FakeResponse(), xform, [], [], 'device-log')

        calls = []
        with patch(
            'corehq.form_processor.submission_post.SubmissionPost.process_device_log',
            new_callable=lambda: process_device_log,
        ):
            _, res = self._submit('device_log.xml')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(calls, [1])

    def test_xform_locked(self):
        from corehq.form_processor.interfaces.processor import FormProcessorInterface
        form_id = 'ad38211be256653bceac8e2156475664'
        proc = FormProcessorInterface(self.domain)
        lock = proc.acquire_lock_for_xform(form_id)
        try:
            _, response = self._submit('simple_form.xml')
        finally:
            lock.release()
        self.assertEqual(response.status_code, 423)


@use_sql_backend
class SubmissionErrorTestSQL(SubmissionErrorTest):

    def test_error_publishing_to_kafka(self):
        sql_patch = patch(
            'corehq.form_processor.backends.sql.processor.FormProcessorSQL.publish_changes_to_kafka',
            side_effect=ValueError
        )
        with sql_patch:
            _, res = self._submit('form_with_case.xml')

        self.assertEqual(res.status_code, 201)
        stubs = UnfinishedSubmissionStub.objects.filter(
            domain=self.domain, saved=True, xform_id=FORM_WITH_CASE_ID
        ).all()
        self.assertEqual(1, len(stubs))

        form = FormAccessors(self.domain).get_form(FORM_WITH_CASE_ID)
        self.assertFalse(form.is_error)
        self.assertTrue(form.initial_processing_complete)

    def test_error_writing_to_blobdb(self):
        error = ConnectionClosedError(endpoint_url='url')
        with self.assertRaises(ConnectionClosedError), patch.object(get_blob_db(), 'put', side_effect=error):
            self._submit('form_with_case.xml')

        stubs = UnfinishedSubmissionStub.objects.filter(
            domain=self.domain, saved=False, xform_id=FORM_WITH_CASE_ID
        ).all()
        self.assertEqual(1, len(stubs))

        old_form = FormAccessors(self.domain).get_form(FORM_WITH_CASE_ID)
        self.assertTrue(old_form.is_error)
        self.assertTrue(old_form.initial_processing_complete)
        expected_problem_message = f'{type(error).__name__}: {error}'
        self.assertEqual(old_form.problem, expected_problem_message)

        _, resp = self._submit('form_with_case.xml')
        self.assertEqual(resp.status_code, 201)
        new_form = FormAccessors(self.domain).get_form(FORM_WITH_CASE_ID)
        self.assertTrue(new_form.is_normal)

        old_form.refresh_from_db()  # can't fetch by form_id since form_id changed
        self.assertEqual(old_form.orig_id, FORM_WITH_CASE_ID)
        self.assertEqual(old_form.problem, expected_problem_message)

    def test_submit_duplicate_blob_not_found(self):
        # https://dimagi-dev.atlassian.net/browse/ICDS-376
        file, res = self._submit('form_with_case.xml')
        self.assertEqual(201, res.status_code)
        self.assertIn("   √   ".encode('utf-8'), res.content)

        form = FormAccessors(self.domain.name).get_form(FORM_WITH_CASE_ID)
        form_attachment_meta = form.get_attachment_meta('form.xml')
        blobdb = get_blob_db()
        with patch.object(blobdb.metadb, 'delete'):
            blobdb.delete(form_attachment_meta.key)

        file, res = self._submit('form_with_case.xml')
        self.assertEqual(res.status_code, 201)
        form = FormAccessors(self.domain.name).get_form(FORM_WITH_CASE_ID)
        deprecated_form = FormAccessors(self.domain.name).get_form(form.deprecated_form_id)
        self.assertTrue(deprecated_form.is_deprecated)

        case = CaseAccessors(self.domain.name).get_case('ad38211be256653bceac8e2156475667')
        transactions = case.transactions
        self.assertEqual(2, len(transactions))
        self.assertTrue(transactions[0].is_form_transaction)
        self.assertTrue(transactions[1].is_case_rebuild)


@contextlib.contextmanager
def failing_signal_handler(error_message):
    def fail(sender, xform, **kwargs):
        raise Exception(error_message)

    successful_form_received.connect(fail)

    try:
        yield
    finally:
        successful_form_received.disconnect(fail)
