from collections import namedtuple
from datetime import datetime, timedelta
from mock import patch

from casexml.apps.case.mock import CaseBlock, CaseFactory

from django.test import TestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.exceptions import DuplicateFormatException, IgnoreDocument
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.repeaters.repeater_generators import FormRepeaterXMLPayloadGenerator, RegisterGenerator, \
    BasePayloadGenerator
from corehq.apps.repeaters.tasks import check_repeaters
from corehq.apps.repeaters.models import (
    CaseRepeater,
    FormRepeater,
    RepeatRecord,
)
from corehq.apps.repeaters.const import MIN_RETRY_WAIT, POST_TIMEOUT, RECORD_SUCCESS_STATE
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.const import DEVICE_LOG_XMLNS


MockResponse = namedtuple('MockResponse', 'status_code reason')
CASE_ID = "ABC123CASEID"
INSTANCE_ID = "XKVB636DFYL38FNX3D38WV5EH"
UPDATE_INSTANCE_ID = "ZYXKVB636DFYL38FNX3D38WV5"
USER_ID = 'mojo-jojo'

XFORM_XML_TEMPLATE = """<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="{}">
    <woman_name>Alpha</woman_name>
    <husband_name>Beta</husband_name>
    <meta>
        <deviceID>O2XLT0WZW97W1A91E2W1Y0NJG</deviceID>
        <timeStart>2011-10-01T15:25:18.404-04</timeStart>
        <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
        <username>admin</username>
        <userID>{}</userID>
        <instanceID>{}</instanceID>
    </meta>
{}
</data>
"""


class BaseRepeaterTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseRepeaterTest, cls).setUpClass()
        case_block = CaseBlock(
            case_id=CASE_ID,
            create=True,
            case_type="repeater_case",
            case_name="ABC 123",
        ).as_string()

        update_case_block = CaseBlock(
            case_id=CASE_ID,
            create=False,
            case_name="ABC 234",
        ).as_string()

        cls.xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            INSTANCE_ID,
            case_block
        )
        cls.update_xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            UPDATE_INSTANCE_ID,
            update_case_block,
        )

    @classmethod
    def post_xml(cls, xml, domain_name):
        submit_form_locally(xml, domain_name)

    @classmethod
    def repeat_records(cls, domain_name):
        return RepeatRecord.all(domain=domain_name, due_before=datetime.utcnow())


class RepeaterTest(BaseRepeaterTest):

    def setUp(self):
        super(RepeaterTest, self).setUp()
        self.domain = "test-domain"
        create_domain(self.domain)
        self.case_repeater = CaseRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.case_repeater.save()
        self.form_repeater = FormRepeater(
            domain=self.domain,
            url='form-repeater-url',
        )
        self.form_repeater.save()
        self.log = []
        self.post_xml(self.xform_xml, self.domain)

    def tearDown(self):
        self.case_repeater.delete()
        self.form_repeater.delete()
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        delete_all_repeat_records()
        super(RepeaterTest, self).tearDown()

    @run_with_all_backends
    def test_skip_device_logs(self):
        devicelog_xml = XFORM_XML_TEMPLATE.format(DEVICE_LOG_XMLNS, USER_ID, '1234', '')
        self.post_xml(devicelog_xml, self.domain)
        repeat_records = RepeatRecord.all(domain=self.domain)
        for repeat_record in repeat_records:
            self.assertNotEqual(repeat_record.payload_id, '1234')

    @run_with_all_backends
    def test_repeater_failed_sends(self):
        """
        This tests records that fail to send three times
        """
        def now():
            return datetime.utcnow()

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now())
        self.assertEqual(len(repeat_records), 2)

        for repeat_record in repeat_records:
            with patch(
                    'corehq.apps.repeaters.models.simple_post_with_cached_timeout',
                    return_value=MockResponse(status_code=404, reason='Not Found')) as mock_post:
                repeat_record.fire()
                self.assertEqual(mock_post.call_count, 3)

        next_check_time = now() + timedelta(minutes=60)

        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=now() + timedelta(minutes=15),
        )
        self.assertEqual(len(repeat_records), 0)

        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=next_check_time,
        )
        self.assertEqual(len(repeat_records), 2)

    @run_with_all_backends
    def test_update_failure_next_check(self):
        now = datetime.utcnow()
        record = RepeatRecord(domain=self.domain, next_check=now)
        self.assertIsNone(record.last_checked)

        record.set_next_try()
        self.assertTrue(record.last_checked > now)
        self.assertEqual(record.next_check, record.last_checked + MIN_RETRY_WAIT)

    @run_with_all_backends
    def test_repeater_successful_send(self):

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())
        mocked_responses = [
            MockResponse(status_code=404, reason='Not Found'),
            MockResponse(status_code=200, reason='No Reason')
        ]
        for repeat_record in repeat_records:
            with patch(
                    'corehq.apps.repeaters.models.simple_post_with_cached_timeout',
                    side_effect=mocked_responses) as mock_post:
                repeat_record.fire()
                self.assertEqual(mock_post.call_count, 2)
                mock_post.assert_any_call(
                    repeat_record.get_payload(),
                    repeat_record.repeater.get_url(repeat_record),
                    headers=repeat_record.repeater.get_headers(repeat_record),
                    force_send=False,
                    timeout=POST_TIMEOUT,
                )

        # The following is pretty fickle and depends on which of
        #   - corehq.apps.repeaters.signals
        #   - casexml.apps.case.signals
        # gets loaded first.
        # This is deterministic but easily affected by minor code changes
        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=datetime.utcnow(),
        )
        for repeat_record in repeat_records:
            self.assertEqual(repeat_record.succeeded, True)
            self.assertEqual(repeat_record.next_check, None)

        self.assertEqual(len(self.repeat_records(self.domain)), 0)

        self.post_xml(self.update_xform_xml, self.domain)
        self.assertEqual(len(self.repeat_records(self.domain)), 2)

    @run_with_all_backends
    def test_check_repeat_records(self):
        self.assertEqual(len(RepeatRecord.all()), 2)

        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 2)

        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

    @run_with_all_backends
    def test_repeat_record_status_check(self):
        self.assertEqual(len(RepeatRecord.all()), 2)

        # Do not trigger cancelled records
        for repeat_record in RepeatRecord.all():
            repeat_record.cancelled = True
            repeat_record.save()
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

        # trigger force send records if not cancelled and tries not exhausted
        for repeat_record in RepeatRecord.all():
            with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout',
                       return_value=MockResponse(status_code=200, reason='')
                       ) as mock_fire:
                repeat_record.fire(force_send=True)
                self.assertEqual(mock_fire.call_count, 1)

        # all records should be in SUCCESS state after force try
        for repeat_record in RepeatRecord.all():
                self.assertEqual(repeat_record.state, RECORD_SUCCESS_STATE)
                self.assertEqual(repeat_record.overall_tries, 1)

        # not trigger records succeeded triggered after cancellation
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)
            for repeat_record in RepeatRecord.all():
                self.assertEqual(repeat_record.state, RECORD_SUCCESS_STATE)

    @run_with_all_backends
    def test_process_repeat_record_locking(self):
        self.assertEqual(len(RepeatRecord.all()), 2)

        with patch('corehq.apps.repeaters.tasks.process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 2)

        with patch('corehq.apps.repeaters.tasks.process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 0)

        records = RepeatRecord.all()
        # Saving should unlock them again by changing the rev
        for record in records:
            record.save()

        with patch('corehq.apps.repeaters.tasks.process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 2)

    @run_with_all_backends
    def test_automatic_cancel_repeat_record(self):
        repeat_record = self.case_repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
        repeat_record.overall_tries = 1
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout', side_effect=Exception('Boom!')):
            repeat_record.fire()
        self.assertEqual(2, repeat_record.overall_tries)
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout', side_effect=Exception('Boom!')):
            repeat_record.fire()
        self.assertEqual(True, repeat_record.cancelled)
        repeat_record.requeue()
        self.assertEqual(0, repeat_record.overall_tries)
        self.assertNotEqual(None, repeat_record.next_check)


class FormPayloadGeneratorTest(BaseRepeaterTest, TestXmlMixin):

    @classmethod
    def setUpClass(cls):
        super(FormPayloadGeneratorTest, cls).setUpClass()

        cls.domain_name = "test-domain"
        cls.domain = create_domain(cls.domain_name)
        cls.repeater = FormRepeater(
            domain=cls.domain_name,
            url="form-repeater-url",
        )
        cls.repeatergenerator = FormRepeaterXMLPayloadGenerator(
            repeater=cls.repeater
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.repeater.delete()
        super(FormPayloadGeneratorTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain_name)
        delete_all_repeat_records()
        super(FormPayloadGeneratorTest, self).tearDown()

    @run_with_all_backends
    def test_get_payload(self):
        self.post_xml(self.xform_xml, self.domain_name)
        payload_doc = FormAccessors(self.domain_name).get_form(INSTANCE_ID)
        payload = self.repeatergenerator.get_payload(None, payload_doc)
        self.assertXmlEqual(self.xform_xml, payload)


class FormRepeaterTest(BaseRepeaterTest, TestXmlMixin):

    @classmethod
    def setUpClass(cls):
        super(FormRepeaterTest, cls).setUpClass()

        cls.domain_name = "test-domain"
        cls.domain = create_domain(cls.domain_name)
        cls.repeater = FormRepeater(
            domain=cls.domain_name,
            url="form-repeater-url",
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.repeater.delete()
        super(FormRepeaterTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain_name)
        delete_all_repeat_records()
        super(FormRepeaterTest, self).tearDown()

    @run_with_all_backends
    def test_payload(self):
        self.post_xml(self.xform_xml, self.domain_name)
        payload = self.repeat_records(self.domain_name).all()[0].get_payload()
        self.assertXMLEqual(self.xform_xml, payload)


class CaseRepeaterTest(BaseRepeaterTest, TestXmlMixin):

    @classmethod
    def setUpClass(cls):
        super(CaseRepeaterTest, cls).setUpClass()

        cls.domain_name = "test-domain"
        cls.domain = create_domain(cls.domain_name)
        cls.repeater = CaseRepeater(
            domain=cls.domain_name,
            url="case-repeater-url",
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.repeater.delete()
        super(CaseRepeaterTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain_name)
        delete_all_repeat_records()
        super(CaseRepeaterTest, self).tearDown()

    @run_with_all_backends
    def test_case_close_format(self):
        # create a case
        self.post_xml(self.xform_xml, self.domain_name)
        payload = self.repeat_records(self.domain_name).all()[0].get_payload()
        self.assertXmlHasXpath(payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(payload, '//*[local-name()="create"]')

        # close the case
        CaseFactory().close_case(CASE_ID)
        close_payload = self.repeat_records(self.domain_name).all()[1].get_payload()
        self.assertXmlHasXpath(close_payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(close_payload, '//*[local-name()="close"]')

    @run_with_all_backends
    def test_excluded_case_types_are_not_forwarded(self):
        self.repeater.white_listed_case_types = ['planet']
        self.repeater.save()

        white_listed_case = CaseBlock(
            case_id="a_case_id",
            create=True,
            case_type="planet",
        ).as_xml()
        CaseFactory(self.domain_name).post_case_blocks([white_listed_case])
        self.assertEqual(1, len(self.repeat_records(self.domain_name).all()))

        non_white_listed_case = CaseBlock(
            case_id="b_case_id",
            create=True,
            case_type="cat",
        ).as_xml()
        CaseFactory(self.domain_name).post_case_blocks([non_white_listed_case])
        self.assertEqual(1, len(self.repeat_records(self.domain_name).all()))

    @run_with_all_backends
    def test_black_listed_user_cases_do_not_forward(self):
        self.repeater.black_listed_users = ['black_listed_user']
        self.repeater.save()
        black_list_user_id = 'black_listed_user'

        # case-creations by black-listed users shouldn't be forwarded
        black_listed_user_case = CaseBlock(
            case_id="b_case_id",
            create=True,
            case_type="planet",
            owner_id="owner",
            user_id=black_list_user_id
        ).as_string()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            black_list_user_id,
            '1234',
            black_listed_user_case,
        )
        self.post_xml(xform_xml, self.domain_name)

        self.assertEqual(0, len(self.repeat_records(self.domain_name).all()))

        # case-creations by normal users should be forwarded
        normal_user_case = CaseBlock(
            case_id="a_case_id",
            create=True,
            case_type="planet",
            owner_id="owner",
            user_id="normal_user"
        ).as_string()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            '6789',
            normal_user_case,
        )
        self.post_xml(xform_xml, self.domain_name)

        self.assertEqual(1, len(self.repeat_records(self.domain_name).all()))

        # case-updates by black-listed users shouldn't be forwarded
        black_listed_user_case = CaseBlock(
            case_id="b_case_id",
            case_type="planet",
            owner_id="owner",
            user_id=black_list_user_id,
        ).as_string()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            black_list_user_id,
            '2345',
            black_listed_user_case,
        )
        self.post_xml(xform_xml, self.domain_name)
        self.assertEqual(1, len(self.repeat_records(self.domain_name).all()))

        # case-updates by normal users should be forwarded
        normal_user_case = CaseBlock(
            case_id="a_case_id",
            case_type="planet",
            owner_id="owner",
            user_id="normal_user",
        ).as_string()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            '3456',
            normal_user_case,
        )
        self.post_xml(xform_xml, self.domain_name)
        self.assertEqual(2, len(self.repeat_records(self.domain_name).all()))


class RepeaterFailureTest(BaseRepeaterTest):

    def setUp(self):
        super(RepeaterFailureTest, self).setUp()
        self.domain_name = "test-domain"
        self.domain = create_domain(self.domain_name)

        self.repeater = CaseRepeater(
            domain=self.domain_name,
            url='case-repeater-url',
        )
        self.repeater.save()
        self.post_xml(self.xform_xml, self.domain_name)

    def tearDown(self):
        self.domain.delete()
        self.repeater.delete()
        delete_all_repeat_records()
        super(RepeaterFailureTest, self).tearDown()

    @run_with_all_backends
    def test_get_payload_exception(self):
        repeat_record = self.repeater.register(CaseAccessors(self.domain_name).get_case(CASE_ID))
        with self.assertRaises(Exception):
            with patch.object(CaseRepeater, 'get_payload', side_effect=Exception('Boom!')):
                repeat_record.fire()

        self.assertEquals(repeat_record.failure_reason, 'Boom!')
        self.assertFalse(repeat_record.succeeded)

    @run_with_all_backends
    def test_failure(self):
        repeat_record = self.repeater.register(CaseAccessors(self.domain_name).get_case(CASE_ID))
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout', side_effect=Exception('Boom!')):
            repeat_record.fire()

        self.assertEquals(repeat_record.failure_reason, 'Boom!')
        self.assertFalse(repeat_record.succeeded)

        # Should be marked as successful after a successful run
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout'):
            repeat_record.fire()

        self.assertTrue(repeat_record.succeeded)


class IgnoreDocumentTest(BaseRepeaterTest):

    @classmethod
    def setUpClass(cls):
        super(IgnoreDocumentTest, cls).setUpClass()

        @RegisterGenerator(FormRepeater, 'new_format', 'XML')
        class NewFormGenerator(BasePayloadGenerator):

            def get_payload(self, repeat_record, payload_doc):
                raise IgnoreDocument

    def setUp(self):
        super(IgnoreDocumentTest, self).setUp()
        self.domain = "test-domain"
        create_domain(self.domain)

        self.repeater = FormRepeater(
            domain=self.domain,
            url='form-repeater-url',
            format='new_format'
        )
        self.repeater.save()

    def tearDown(self):
        self.repeater.delete()
        delete_all_repeat_records()
        super(IgnoreDocumentTest, self).tearDown()

    @run_with_all_backends
    def test_ignore_document(self):
        """
        When get_payload raises IgnoreDocument, fire should call update_success
        """
        repeat_records = RepeatRecord.all(
            domain=self.domain,
        )
        for repeat_record_ in repeat_records:
            repeat_record_.fire()

            self.assertIsNone(repeat_record_.next_check)
            self.assertTrue(repeat_record_.succeeded)


class TestRepeaterFormat(BaseRepeaterTest):

    @classmethod
    def setUpClass(cls):
        super(TestRepeaterFormat, cls).setUpClass()
        cls.payload = 'some random case'

        @RegisterGenerator(CaseRepeater, 'new_format', 'XML')
        class NewCaseGenerator(BasePayloadGenerator):

            def get_payload(self, repeat_record, payload_doc):
                return cls.payload

    def setUp(self):
        super(TestRepeaterFormat, self).setUp()
        self.domain = "test-domain"
        create_domain(self.domain)
        self.post_xml(self.xform_xml, self.domain)

        self.repeater = CaseRepeater(
            domain=self.domain,
            url='case-repeater-url',
            format='new_format',
        )
        self.repeater.save()

    def tearDown(self):
        self.repeater.delete()
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        delete_all_repeat_records()
        super(TestRepeaterFormat, self).tearDown()

    def test_new_format_same_name(self):
        with self.assertRaises(DuplicateFormatException):
            @RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=False)
            class NewCaseGenerator(BasePayloadGenerator):

                def get_payload(self, repeat_record, payload_doc):
                    return self.payload

    def test_new_format_second_default(self):
        with self.assertRaises(DuplicateFormatException):
            @RegisterGenerator(CaseRepeater, 'rubbish', 'XML', is_default=True)
            class NewCaseGenerator(BasePayloadGenerator):

                def get_payload(self, repeat_record, payload_doc):
                    return self.payload

    @run_with_all_backends
    def test_new_format_payload(self):
        repeat_record = self.repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout') as mock_post:
            repeat_record.fire()
            headers = self.repeater.get_headers(repeat_record)
            mock_post.assert_called_with(
                self.payload,
                self.repeater.url,
                headers=headers,
                force_send=False,
                timeout=POST_TIMEOUT,
            )
