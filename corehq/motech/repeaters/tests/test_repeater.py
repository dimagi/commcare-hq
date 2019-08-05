from __future__ import absolute_import
from __future__ import unicode_literals

import json
import uuid
from collections import namedtuple
from datetime import datetime, timedelta

import attr
from django.test import TestCase, override_settings, SimpleTestCase

from mock import patch, Mock
from six.moves import range

from casexml.apps.case.mock import CaseBlock, CaseFactory
from casexml.apps.case.xform import get_case_ids_from_form
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.receiverwrapper.exceptions import DuplicateFormatException, IgnoreDocument
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.motech.repeaters.const import MIN_RETRY_WAIT, POST_TIMEOUT, RECORD_SUCCESS_STATE
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from corehq.motech.repeaters.models import (
    CaseRepeater,
    FormRepeater,
    LocationRepeater,
    RepeatRecord,
    ShortFormRepeater,
    UserRepeater,
    Repeater,
)
from corehq.motech.repeaters.repeater_generators import (
    BasePayloadGenerator,
    FormRepeaterXMLPayloadGenerator,
    RegisterGenerator,
)
from corehq.motech.repeaters.tasks import check_repeaters, process_repeat_record

MockResponse = namedtuple('MockResponse', 'status_code reason')
CASE_ID = "ABC123CASEID"
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

        cls.instance_id = uuid.uuid4().hex
        cls.xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            cls.instance_id,
            case_block
        )
        cls.update_xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            uuid.uuid4().hex,
            update_case_block,
        )

    @classmethod
    def post_xml(cls, xml, domain_name):
        return submit_form_locally(xml, domain_name)

    @classmethod
    def repeat_records(cls, domain_name):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.all(domain=domain_name, due_before=later)


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

        with patch('corehq.motech.repeaters.models.simple_post',
                   return_value=MockResponse(status_code=500, reason="Borked")) as mock_fire:
            self.post_xml(self.xform_xml, self.domain)
            self.initial_fire_call_count = mock_fire.call_count

    def tearDown(self):
        self.case_repeater.delete()
        self.form_repeater.delete()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        delete_all_repeat_records()
        super(RepeaterTest, self).tearDown()

    def repeat_records(self):
        return super(RepeaterTest, self).repeat_records(self.domain)

    @run_with_all_backends
    def test_skip_device_logs(self):
        devicelog_xml = XFORM_XML_TEMPLATE.format(DEVICE_LOG_XMLNS, USER_ID, '1234', '')
        self.post_xml(devicelog_xml, self.domain)
        for repeat_record in self.repeat_records():
            self.assertNotEqual(repeat_record.payload_id, '1234')

    @run_with_all_backends
    def test_skip_duplicates(self):
        """
        Ensure that submitting a duplicate form does not create extra RepeatRecords
        """
        self.assertEqual(len(self.repeat_records()), 2)
        # this form is already submitted during setUp so a second submission should be a duplicate
        form = self.post_xml(self.xform_xml, self.domain).xform
        self.assertTrue(form.is_duplicate)
        self.assertEqual(len(self.repeat_records()), 2)

    @run_with_all_backends
    def test_repeater_failed_sends(self):
        """
        This tests records that fail are requeued later
        """
        def now():
            return datetime.utcnow()

        repeat_records = self.repeat_records()
        self.assertEqual(len(repeat_records), 2)

        for repeat_record in repeat_records:
            with patch(
                    'corehq.motech.repeaters.models.simple_post',
                    return_value=MockResponse(status_code=404, reason='Not Found')) as mock_post:
                repeat_record.fire()
                self.assertEqual(mock_post.call_count, 1)

        # Enqueued repeat records have next_check incremented by 48 hours
        next_check_time = now() + timedelta(minutes=60) + timedelta(hours=48)

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

        attempt = record.make_set_next_try_attempt(None)
        record.add_attempt(attempt)
        self.assertTrue(record.last_checked > now)
        self.assertEqual(record.next_check, record.last_checked + MIN_RETRY_WAIT)

    @run_with_all_backends
    def test_repeater_successful_send(self):

        repeat_records = self.repeat_records()

        for repeat_record in repeat_records:
            with patch(
                    'corehq.motech.repeaters.models.simple_post',
                    return_value=MockResponse(status_code=200, reason='No Reason')) as mock_post:
                repeat_record.fire()
                self.assertEqual(mock_post.call_count, 1)
                mock_post.assert_any_call(
                    repeat_record.get_payload(),
                    repeat_record.repeater.get_url(repeat_record),
                    headers=repeat_record.repeater.get_headers(repeat_record),
                    timeout=POST_TIMEOUT,
                    auth=repeat_record.repeater.get_auth(),
                    verify=repeat_record.repeater.verify,
                )

        # The following is pretty fickle and depends on which of
        #   - corehq.motech.repeaters.signals
        #   - casexml.apps.case.signals
        # gets loaded first.
        # This is deterministic but easily affected by minor code changes
        repeat_records = self.repeat_records()
        for repeat_record in repeat_records:
            self.assertEqual(repeat_record.succeeded, True)
            self.assertEqual(repeat_record.next_check, None)

        self.assertEqual(len(self.repeat_records()), 0)

        self.post_xml(self.update_xform_xml, self.domain)
        self.assertEqual(len(self.repeat_records()), 2)

    @run_with_all_backends
    def test_check_repeat_records(self):
        self.assertEqual(len(self.repeat_records()), 2)
        self.assertEqual(self.initial_fire_call_count, 2)

        with patch('corehq.motech.repeaters.models.simple_post') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

    @run_with_all_backends
    def test_repeat_record_status_check(self):
        self.assertEqual(len(self.repeat_records()), 2)

        # Do not trigger cancelled records
        for repeat_record in self.repeat_records():
            repeat_record.cancelled = True
            repeat_record.save()
        with patch('corehq.motech.repeaters.models.simple_post') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

        # trigger force send records if not cancelled and tries not exhausted
        for repeat_record in self.repeat_records():
            with patch('corehq.motech.repeaters.models.simple_post',
                       return_value=MockResponse(status_code=200, reason='')
                       ) as mock_fire:
                repeat_record.fire(force_send=True)
                self.assertEqual(mock_fire.call_count, 1)

        # all records should be in SUCCESS state after force try
        for repeat_record in self.repeat_records():
                self.assertEqual(repeat_record.state, RECORD_SUCCESS_STATE)
                self.assertEqual(repeat_record.overall_tries, 1)

        # not trigger records succeeded triggered after cancellation
        with patch('corehq.motech.repeaters.models.simple_post') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)
            for repeat_record in self.repeat_records():
                self.assertEqual(repeat_record.state, RECORD_SUCCESS_STATE)

    @run_with_all_backends
    def test_process_repeat_record_locking(self):
        self.assertEqual(len(self.repeat_records()), 2)

        with patch('corehq.motech.repeaters.tasks.process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 0)

        for record in self.repeat_records():
            # Resetting next_check should allow them to be requeued
            record.next_check = datetime.utcnow()
            record.save()

        with patch('corehq.motech.repeaters.tasks.process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 2)

    @run_with_all_backends
    def test_automatic_cancel_repeat_record(self):
        repeat_record = self.case_repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
        self.assertEqual(1, repeat_record.overall_tries)
        with patch('corehq.motech.repeaters.models.simple_post', side_effect=Exception('Boom!')):
            for __ in range(repeat_record.max_possible_tries - repeat_record.overall_tries):
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
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain_name)
        delete_all_repeat_records()
        super(FormPayloadGeneratorTest, self).tearDown()

    @run_with_all_backends
    def test_get_payload(self):
        self.post_xml(self.xform_xml, self.domain_name)
        payload_doc = FormAccessors(self.domain_name).get_form(self.instance_id)
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
        repeat_records = self.repeat_records(self.domain_name).all()
        payload = repeat_records[0].get_payload().decode('utf-8')
        self.assertXMLEqual(self.xform_xml, payload)


class ShortFormRepeaterTest(BaseRepeaterTest, TestXmlMixin):

    @classmethod
    def setUpClass(cls):
        super(ShortFormRepeaterTest, cls).setUpClass()

        cls.domain_name = "test-domain"
        cls.domain = create_domain(cls.domain_name)
        cls.repeater = ShortFormRepeater(
            domain=cls.domain_name,
            url="short-form-repeater-url",
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.repeater.delete()
        super(ShortFormRepeaterTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain_name)
        delete_all_repeat_records()
        super(ShortFormRepeaterTest, self).tearDown()

    @run_with_all_backends
    def test_payload(self):
        form = self.post_xml(self.xform_xml, self.domain_name).xform
        repeat_records = self.repeat_records(self.domain_name).all()
        payload = repeat_records[0].get_payload()
        self.assertEqual(json.loads(payload), {
            'received_on': json_format_datetime(form.received_on),
            'form_id': form.form_id,
            'case_ids': list(get_case_ids_from_form(form))
        })


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
        repeat_records = self.repeat_records(self.domain_name).all()
        payload = repeat_records[0].get_payload()
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
        with patch('corehq.motech.repeaters.models.simple_post', side_effect=Exception('Boom!')):
            repeat_record.fire()

        self.assertEquals(repeat_record.failure_reason, 'Boom!')
        self.assertFalse(repeat_record.succeeded)

        # Should be marked as successful after a successful run
        with patch('corehq.motech.repeaters.models.simple_post') as mock_simple_post:
            mock_simple_post.return_value.status_code = 200
            repeat_record.fire()

        self.assertTrue(repeat_record.succeeded)


class IgnoreDocumentTest(BaseRepeaterTest):

    @classmethod
    def setUpClass(cls):
        super(IgnoreDocumentTest, cls).setUpClass()

        class NewFormGenerator(BasePayloadGenerator):
            format_name = 'new_format'
            format_label = 'XML'

            def get_payload(self, repeat_record, payload_doc):
                raise IgnoreDocument

        RegisterGenerator.get_collection(FormRepeater).add_new_format(NewFormGenerator)

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

        class NewCaseGenerator(BasePayloadGenerator):
            format_name = 'new_format'
            format_label = 'XML'
            deprecated_format_names = ('new_format_alias',)

            def get_payload(self, repeat_record, payload_doc):
                return cls.payload

        RegisterGenerator.get_collection(CaseRepeater).add_new_format(NewCaseGenerator)
        cls.new_generator = NewCaseGenerator

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
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        delete_all_repeat_records()
        super(TestRepeaterFormat, self).tearDown()

    def test_new_format_same_name(self):
        class NewCaseGenerator(BasePayloadGenerator):
            format_name = 'case_xml'
            format_label = 'XML'

            def get_payload(self, repeat_record, payload_doc):
                return self.payload

        with self.assertRaises(DuplicateFormatException):
            RegisterGenerator.get_collection(CaseRepeater).add_new_format(NewCaseGenerator)

    def test_new_format_second_default(self):
        class NewCaseGenerator(BasePayloadGenerator):
            format_name = 'rubbish'
            format_label = 'XML'

            def get_payload(self, repeat_record, payload_doc):
                return self.payload

        with self.assertRaises(DuplicateFormatException):
            RegisterGenerator.get_collection(CaseRepeater).add_new_format(NewCaseGenerator, is_default=True)

    @run_with_all_backends
    def test_new_format_payload(self):
        repeat_record = self.repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
        with patch('corehq.motech.repeaters.models.simple_post') as mock_post:
            mock_post.return_value.status_code = 200
            repeat_record.fire()
            headers = self.repeater.get_headers(repeat_record)
            mock_post.assert_called_with(
                self.payload,
                self.repeater.url,
                headers=headers,
                timeout=POST_TIMEOUT,
                auth=self.repeater.get_auth(),
                verify=self.repeater.verify,
            )

    def test_get_format_by_deprecated_name(self):
        self.assertIsInstance(CaseRepeater(
            domain=self.domain,
            url='case-repeater-url',
            format='new_format_alias',
        ).generator, self.new_generator)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class UserRepeaterTest(TestCase):
    domain = 'user-repeater'

    def setUp(self):
        super(UserRepeaterTest, self).setUp()
        self.repeater = UserRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(UserRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()

    def repeat_records(self):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.all(domain=self.domain, due_before=later)

    def make_user(self, username):
        user = CommCareUser.create(
            self.domain,
            "{}@{}.commcarehq.org".format(username, self.domain),
            "123",
        )
        self.addCleanup(user.delete)
        return user

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        user = self.make_user("bselmy")
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            json.loads(record.get_payload()),
            {
                'id': user._id,
                'username': user.username,
                'first_name': '',
                'last_name': '',
                'default_phone_number': None,
                'user_data': {'commcare_project': self.domain},
                'groups': [],
                'phone_numbers': [],
                'email': '',
                'resource_uri': '/a/user-repeater/api/v0.5/user/{}/'.format(user._id),
            }
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LocationRepeaterTest(TestCase):
    domain = 'location-repeater'

    def setUp(self):
        super(LocationRepeaterTest, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.repeater = LocationRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()
        self.location_type = LocationType.objects.create(
            domain=self.domain,
            name="city",
        )

    def tearDown(self):
        super(LocationRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()
        self.domain_obj.delete()

    def repeat_records(self):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.all(domain=self.domain, due_before=later)

    def make_location(self, name):
        location = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=self.location_type,
        )
        self.addCleanup(location.delete)
        return location

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        location = self.make_location('kings_landing')
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            json.loads(record.get_payload()),
            {
                '_id': location.location_id,
                'doc_type': 'Location',
                'domain': self.domain,
                'external_id': None,
                'is_archived': False,
                'last_modified': location.last_modified.isoformat(),
                'latitude': None,
                'lineage': [],
                'location_id': location.location_id,
                'location_type': 'city',
                'location_type_code': 'city',
                'longitude': None,
                'metadata': {},
                'name': location.name,
                'parent_location_id': None,
                'site_code': location.site_code,
            }
        )


class TestRepeaterPause(BaseRepeaterTest):
    def setUp(self):
        super(TestRepeaterPause, self).setUp()
        self.domain_name = "test-domain"
        self.domain = create_domain(self.domain_name)

        self.repeater = CaseRepeater(
            domain=self.domain_name,
            url='case-repeater-url',
        )
        self.repeater.save()
        self.post_xml(self.xform_xml, self.domain_name)

    @run_with_all_backends
    def test_trigger_when_paused(self):
        # not paused
        with patch.object(RepeatRecord, 'fire') as mock_fire:
            with patch.object(RepeatRecord, 'postpone_by') as mock_postpone_fire:
                # calls process_repeat_record():
                self.repeat_record = self.repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
                self.assertEqual(mock_fire.call_count, 1)
                self.assertEqual(mock_postpone_fire.call_count, 0)

                # paused
                self.repeater.pause()
                # re fetch repeat record
                repeat_record_id = self.repeat_record.get_id
                self.repeat_record = RepeatRecord.get(repeat_record_id)
                process_repeat_record(self.repeat_record)
                self.assertEqual(mock_fire.call_count, 1)
                self.assertEqual(mock_postpone_fire.call_count, 1)

                # resumed
                self.repeater.resume()
                # re fetch repeat record
                repeat_record_id = self.repeat_record.get_id
                self.repeat_record = RepeatRecord.get(repeat_record_id)
                process_repeat_record(self.repeat_record)
                self.assertEqual(mock_fire.call_count, 2)
                self.assertEqual(mock_postpone_fire.call_count, 1)

    def tearDown(self):
        self.domain.delete()
        self.repeater.delete()
        delete_all_repeat_records()
        super(TestRepeaterPause, self).tearDown()


class TestRepeaterDeleted(BaseRepeaterTest):
    def setUp(self):
        super(TestRepeaterDeleted, self).setUp()
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
        super(TestRepeaterDeleted, self).tearDown()

    @run_with_all_backends
    def test_trigger_when_deleted(self):
        self.repeater.retire()

        with patch.object(RepeatRecord, 'fire') as mock_fire:
            self.repeat_record = self.repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
            process_repeat_record(self.repeat_record)
            self.assertEqual(mock_fire.call_count, 0)
            self.assertEqual(self.repeat_record.doc_type, "RepeatRecord-Deleted")

    @run_with_all_backends
    def test_paused_then_deleted(self):
        self.repeater.pause()
        self.repeater.retire()

        with patch.object(RepeatRecord, 'fire') as mock_fire:
            self.repeat_record = self.repeater.register(CaseAccessors(self.domain).get_case(CASE_ID))
            process_repeat_record(self.repeat_record)
            self.assertEqual(mock_fire.call_count, 0)
            self.assertEqual(self.repeat_record.doc_type, "RepeatRecord-Deleted")


@attr.s
class Response:
    status_code = attr.ib()
    reason = attr.ib()
    content = attr.ib(default=None)
    encoding = attr.ib(default='ascii')

    @property
    def text(self):
        return '' if self.content is None else str(self.content, self.encoding, errors='replace')


class HandleResponseTests(SimpleTestCase):

    def setUp(self):

        class DummyRepeater(Repeater):

            @property
            def generator(self):
                return FormRepeaterXMLPayloadGenerator(self)

            def payload_doc(self, repeat_record):
                return {}

        self.repeater = DummyRepeater(
            domain="test-domain",
            url="https://example.com/api/",
        )
        self.repeat_record = Mock()

    def test_handle_ok_response(self):
        response = Response(status_code=200, reason='OK', content=b'OK')
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_called()
        self.repeat_record.handle_failure.assert_not_called()

    def test_handle_true_response(self):
        response = True
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_called()
        self.repeat_record.handle_failure.assert_not_called()

    def test_handle_none_response(self):
        response = None
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_failure.assert_called()

    def test_handle_500_response(self):
        response = Response(status_code=500, reason='The core is exposed')
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_failure.assert_called()

    def test_handle_exception(self):
        err = Exception('The core is exposed')
        self.repeater.handle_response(err, self.repeat_record)

        self.repeat_record.handle_exception.assert_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_failure.assert_not_called()


class FormatResponseTests(SimpleTestCase):

    def test_content_is_ascii(self):
        response = Response(
            status_code=200,
            reason='OK',
            content=b'3.6 roentgen. Not great. Not terrible.'
        )
        formatted = RepeatRecord._format_response(response)
        self.assertEqual(formatted, '200: OK.\n3.6 roentgen. Not great. Not terrible.')

    def test_encoding_is_not_ascii(self):
        response = Response(
            status_code=200,
            reason='OK',
            content=b'3,6 \xe1\xa8\xd4\xe5\xac\xa8\xd4\xa0 \xd5\xa8 \xb5\xd6\xe1\xd6\xf5\xd6. '
                    b'\xd5\xa8 \xe3\xe5\xe1\xa0\xf5\xd4\xd6',
            encoding='cp855'
        )
        formatted = RepeatRecord._format_response(response)
        self.assertEqual(formatted, '200: OK.\n3,6 рентгена Не хорошо. Не страшно')

    def test_content_is_None(self):
        response = Response(500, 'The core is exposed')
        formatted = RepeatRecord._format_response(response)
        self.assertEqual(formatted, '500: The core is exposed.\n')
