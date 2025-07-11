import json
import uuid
from collections import namedtuple
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

import attr
from requests import RequestException

from casexml.apps.case.mock import CaseBlock, CaseFactory
from casexml.apps.case.xform import get_case_ids_from_form
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.receiverwrapper.exceptions import (
    DuplicateFormatException,
    IgnoreDocument,
)
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.pillow import (
    ConfigurableReportPillowProcessor,
    ConfigurableReportTableManager,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
    get_sample_doc_and_indicators,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.models import ConnectionSettings
from corehq.pillows.case import get_case_pillow
from corehq.util.json import CommCareJSONEncoder
from corehq.util.test_utils import flag_enabled

from ..const import (
    MAX_BACKOFF_ATTEMPTS,
    MAX_RETRY_WAIT,
    MIN_REPEATER_RETRY_WAIT,
    MIN_RETRY_WAIT,
    State,
)
from ..models import (
    CaseRepeater,
    DataSourceRepeater,
    DataSourceUpdate,
    FormRepeater,
    LocationRepeater,
    Repeater,
    RepeatRecord,
    ShortFormRepeater,
    UserRepeater,
    _get_retry_interval,
    format_response,
)
from ..repeater_generators import (
    BasePayloadGenerator,
    FormRepeaterXMLPayloadGenerator,
    RegisterGenerator,
)
from ..tasks import _process_repeat_record, check_repeaters

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


class BaseRepeaterTest(TestCase, DomainSubscriptionMixin):
    domain = 'base-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.case_block = CaseBlock(
            case_id=CASE_ID,
            create=True,
            case_type="repeater_case",
            case_name="ABC 123",
        ).as_text()

        cls.update_case_block = CaseBlock(
            case_id=CASE_ID,
            create=False,
            case_name="ABC 234",
        ).as_text()

        cls.instance_id = uuid.uuid4().hex
        cls.xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            cls.instance_id,
            cls.case_block
        )
        cls.update_xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            uuid.uuid4().hex,
            cls.update_case_block,
        )

        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(cls.domain_obj.delete)

        # DATA_FORWARDING is on PRO and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)
        cls.addClassCleanup(cls.teardown_subscriptions)

    def enqueued_repeat_records(self):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)


class RepeaterTest(BaseRepeaterTest):
    domain = "repeater-test"

    def setUp(self):
        super(RepeaterTest, self).setUp()
        self.case_connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.case_repeater = CaseRepeater(
            domain=self.domain,
            connection_settings_id=self.case_connx.id,
            format='case_json',
        )
        self.case_repeater.save()

        self.form_connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='form-repeater-url',
        )
        self.form_repeater = FormRepeater(
            domain=self.domain,
            connection_settings_id=self.form_connx.id,
            format='form_json',
        )
        self.form_repeater.save()
        self.log = []

        with patch('corehq.motech.repeaters.models.simple_request',
                   # SERVICE_UNAVAILABLE is a response that is retried
                   # See ..models.HTTP_STATUS_BACK_OFF
                   return_value=MockResponse(
                       status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
                       reason=HTTPStatus.SERVICE_UNAVAILABLE.description,
                   )) as mock_fire:
            submit_form_locally(self.xform_xml, self.domain)
            self.initial_fire_call_count = mock_fire.call_count

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(RepeaterTest, self).tearDown()

    # whatever value specified will be doubled since both case and form repeater are active
    def _create_additional_repeat_records(self, count):
        for _ in range(count):
            instance_id = uuid.uuid4().hex
            xform_xml = XFORM_XML_TEMPLATE.format(
                "https://www.commcarehq.org/test/repeater/",
                USER_ID,
                instance_id,
                self.case_block
            )
            with patch('corehq.motech.repeaters.models.simple_request',
                       return_value=MockResponse(
                           status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
                           reason=HTTPStatus.SERVICE_UNAVAILABLE.description,
                       )):
                submit_form_locally(xform_xml, self.domain)

    def test_initial_repeat_records(self):
        repeat_records = self.enqueued_repeat_records()
        assert len(repeat_records) == 2

    def test_skip_device_logs(self):
        devicelog_xml = XFORM_XML_TEMPLATE.format(DEVICE_LOG_XMLNS, USER_ID, '1234', '')
        submit_form_locally(devicelog_xml, self.domain)
        for repeat_record in self.enqueued_repeat_records():
            self.assertNotEqual(repeat_record.payload_id, '1234')

    def test_skip_duplicates(self):
        """
        Ensure that submitting a duplicate form does not create extra RepeatRecords
        """
        self.assertEqual(len(self.enqueued_repeat_records()), 2)
        # this form is already submitted during setUp so a second submission should be a duplicate
        form = submit_form_locally(self.xform_xml, self.domain).xform
        self.assertTrue(form.is_duplicate)
        self.assertEqual(len(self.enqueued_repeat_records()), 2)

    def test_server_failure_resends(self):
        """
        This tests records that encounter server errors are requeued later
        """
        def now():
            return datetime.utcnow()

        repeat_records = self.enqueued_repeat_records()
        self.assertEqual(len(repeat_records), 2)

        for repeat_record in repeat_records:
            with patch(
                'corehq.motech.repeaters.models.simple_request',
                return_value=MockResponse(status_code=503, reason='Service Unavailable')
            ) as mock_request:
                repeat_record.fire()
                self.assertEqual(mock_request.call_count, 1)

        # Enqueued repeat records have next_check incremented by 48 hours
        next_check_time = now() + timedelta(minutes=60) + timedelta(hours=48)

        repeat_records = RepeatRecord.objects.filter(
            domain=self.domain,
            next_check__lt=now() + timedelta(minutes=15),
        )
        self.assertEqual(len(repeat_records), 0)

        repeat_records = RepeatRecord.objects.filter(
            domain=self.domain,
            next_check__lt=next_check_time,
        )
        self.assertEqual(len(repeat_records), 2)

    def test_bad_payload_invalid(self):
        with patch(
            'corehq.motech.repeaters.models.simple_request',
            return_value=MockResponse(status_code=401, reason='Unauthorized')
        ):
            for repeat_record in self.enqueued_repeat_records():
                repeat_record.fire()

        for repeat_record in self.enqueued_repeat_records():
            self.assertEqual(repeat_record.state, State.InvalidPayload)

    def test_bad_request_fail(self):
        with patch(
            'corehq.motech.repeaters.models.simple_request',
            return_value=MockResponse(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
                reason=HTTPStatus.SERVICE_UNAVAILABLE.description,
            )
        ):
            for repeat_record in self.enqueued_repeat_records():
                repeat_record.fire()

        for repeat_record in self.enqueued_repeat_records():
            self.assertEqual(repeat_record.state, State.Fail)

    def test_update_failure_next_check(self):
        now = datetime.utcnow()
        record = RepeatRecord.objects.create(
            domain=self.domain,
            repeater_id=self.case_repeater.repeater_id,
            registered_at=now,
            next_check=now,
        )
        self.assertIsNone(record.last_checked)

        record.add_server_failure_attempt("error")
        self.assertGreater(record.last_checked, now)
        self.assertEqual(record.next_check, record.last_checked + MIN_RETRY_WAIT)

    def test_repeater_successful_send(self):

        repeat_records = self.enqueued_repeat_records()

        for repeat_record in repeat_records:
            with patch('corehq.motech.repeaters.models.simple_request') as mock_request, \
                    patch.object(ConnectionSettings, 'get_auth_manager') as mock_manager:
                mock_request.return_value.status_code = 200
                mock_manager.return_value = 'MockAuthManager'
                repeat_record.fire()
                self.assertEqual(mock_request.call_count, 1)
                mock_request.assert_called_with(
                    self.domain,
                    repeat_record.repeater.get_url(repeat_record),
                    repeat_record.get_payload(),
                    headers=repeat_record.repeater.get_headers(repeat_record),
                    auth_manager='MockAuthManager',
                    verify=repeat_record.repeater.verify,
                    notify_addresses=[],
                    payload_id=repeat_record.payload_id,
                    method="POST",
                )

        # The following is pretty fickle and depends on which of
        #   - corehq.motech.repeaters.signals
        #   - casexml.apps.case.signals
        # gets loaded first.
        # This is deterministic but easily affected by minor code changes
        repeat_records = self.enqueued_repeat_records()
        for repeat_record in repeat_records:
            self.assertEqual(repeat_record.state, State.Success)
            self.assertEqual(repeat_record.next_check, None)

        self.assertEqual(len(self.enqueued_repeat_records()), 0)

        submit_form_locally(self.update_xform_xml, self.domain)
        self.assertEqual(len(self.enqueued_repeat_records()), 2)

    def test_check_repeat_records(self):
        self.assertEqual(len(self.enqueued_repeat_records()), 2)
        self.assertEqual(self.initial_fire_call_count, 2)

        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

    def test_repeat_record_status_check(self):
        self.assertEqual(len(self.enqueued_repeat_records()), 2)

        # Do not trigger cancelled records
        for repeat_record in self.enqueued_repeat_records():
            repeat_record.state = State.Cancelled
            repeat_record.next_check = None
            repeat_record.save()
        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

        # trigger force send records if not cancelled and tries not exhausted
        for repeat_record in self.enqueued_repeat_records():
            with patch('corehq.motech.repeaters.models.simple_request',
                       return_value=MockResponse(status_code=200, reason='')
                       ) as mock_fire:
                repeat_record.fire(force_send=True)
                self.assertEqual(mock_fire.call_count, 1)

        # all records should be in SUCCESS state after force try
        for repeat_record in self.enqueued_repeat_records():
            self.assertEqual(repeat_record.state, State.Success)
            self.assertEqual(repeat_record.num_attempts, 1)

        # not trigger records succeeded triggered after cancellation
        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire:
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)
            for repeat_record in self.enqueued_repeat_records():
                self.assertEqual(repeat_record.state, State.Success)

    def test_retry_process_repeat_record_locking(self):
        self.assertEqual(len(self.enqueued_repeat_records()), 2)

        with patch('corehq.motech.repeaters.tasks.retry_process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 0)

        for record in self.enqueued_repeat_records():
            # Resetting next_check should allow them to be requeued
            record.next_check = datetime.utcnow()
            record.save()

        with patch('corehq.motech.repeaters.tasks.retry_process_repeat_record') as mock_process:
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 2)

    def test_automatic_cancel_repeat_record(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        self.case_repeater.register(case)
        rr = self.case_repeater.repeat_records.last()
        # Fetch the revision that was updated:
        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(1, repeat_record.num_attempts)
        with patch('corehq.motech.repeaters.models.simple_request', side_effect=Exception('Boom!')):
            for __ in range(repeat_record.max_possible_tries - repeat_record.num_attempts):
                repeat_record.fire()
        self.assertEqual(repeat_record.state, State.Cancelled)
        repeat_record.requeue()
        self.assertEqual(repeat_record.max_possible_tries - repeat_record.num_attempts, MAX_BACKOFF_ATTEMPTS)
        self.assertNotEqual(None, repeat_record.next_check)

    def test_check_repeat_records_ignores_future_retries_using_multiple_partitions(self):
        self._create_additional_repeat_records(9)
        # 10 form submission payloads and 1 case create payload:
        self.assertEqual(len(self.enqueued_repeat_records()), 11)

        with patch('corehq.motech.repeaters.models.simple_request') as mock_retry, \
             patch('corehq.motech.repeaters.tasks.CHECK_REPEATERS_PARTITION_COUNT', 10):
            check_repeaters()
            self.assertEqual(mock_retry.delay.call_count, 0)

    def test_repeat_record_status_check_using_multiple_partitions(self):
        self._create_additional_repeat_records(9)
        self.assertEqual(len(self.enqueued_repeat_records()), 11)

        # Do not trigger cancelled records
        for repeat_record in self.enqueued_repeat_records():
            repeat_record.state = State.Cancelled
            repeat_record.next_check = None
            repeat_record.save()
        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire, \
             patch('corehq.motech.repeaters.tasks.CHECK_REPEATERS_PARTITION_COUNT', 10):
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)

        # trigger force send records if not cancelled and tries not exhausted
        for repeat_record in self.enqueued_repeat_records():
            with patch('corehq.motech.repeaters.models.simple_request',
                       return_value=MockResponse(status_code=200, reason='')
                       ) as mock_fire:
                repeat_record.fire(force_send=True)
                self.assertEqual(mock_fire.call_count, 1)

        # all records should be in SUCCESS state after force try
        for repeat_record in self.enqueued_repeat_records():
            self.assertEqual(repeat_record.state, State.Success)
            self.assertEqual(repeat_record.num_attempts, 1)

        # not trigger records succeeded triggered after cancellation
        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire, \
             patch('corehq.motech.repeaters.tasks.CHECK_REPEATERS_PARTITION_COUNT', 10):
            check_repeaters()
            self.assertEqual(mock_fire.call_count, 0)
            for repeat_record in self.enqueued_repeat_records():
                self.assertEqual(repeat_record.state, State.Success)

    def test_check_repeaters_successfully_retries_using_multiple_partitions(self):
        self._create_additional_repeat_records(9)
        self.assertEqual(len(self.enqueued_repeat_records()), 11)

        with patch('corehq.motech.repeaters.tasks.retry_process_repeat_record') as mock_process, \
             patch('corehq.motech.repeaters.tasks.CHECK_REPEATERS_PARTITION_COUNT', 10):
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 0)

        for record in self.enqueued_repeat_records():
            # set next_check to a time older than now
            record.next_check = datetime.utcnow() - timedelta(hours=1)
            record.save()

        with patch('corehq.motech.repeaters.tasks.retry_process_repeat_record') as mock_process, \
             patch('corehq.motech.repeaters.tasks.CHECK_REPEATERS_PARTITION_COUNT', 10):
            check_repeaters()
            self.assertEqual(mock_process.delay.call_count, 11)


class FormPayloadGeneratorTest(BaseRepeaterTest, TestXmlMixin):
    domain = "form-payload"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url="form-repeater-url",
        )
        cls.repeater = FormRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
            format='form_xml',
        )
        cls.repeatergenerator = FormRepeaterXMLPayloadGenerator(
            repeater=cls.repeater
        )
        cls.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super().tearDown()

    def test_get_payload(self):
        submit_form_locally(self.xform_xml, self.domain)
        payload_doc = XFormInstance.objects.get_form(self.instance_id, self.domain)
        payload = self.repeatergenerator.get_payload(None, payload_doc)
        self.assertXmlEqual(self.xform_xml, payload)


class FormRepeaterTest(BaseRepeaterTest, TestXmlMixin):
    domain = "form-repeater"

    @classmethod
    def setUpClass(cls):
        super(FormRepeaterTest, cls).setUpClass()
        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url="form-repeater-url",
        )
        cls.repeater = FormRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
            format='form_xml',
        )
        cls.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super(FormRepeaterTest, self).tearDown()

    def test_payload(self):
        submit_form_locally(self.xform_xml, self.domain)
        repeat_records = self.enqueued_repeat_records()
        payload = repeat_records[0].get_payload().decode('utf-8')
        self.assertXMLEqual(self.xform_xml, payload)


class ShortFormRepeaterTest(BaseRepeaterTest, TestXmlMixin):
    domain = "sh-form-rep"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url="short-form-repeater-url",
        )
        cls.repeater = ShortFormRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
        )
        cls.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super().tearDown()

    def test_payload(self):
        form = submit_form_locally(self.xform_xml, self.domain).xform
        repeat_records = self.enqueued_repeat_records()
        payload = repeat_records[0].get_payload()
        self.assertEqual(json.loads(payload), {
            'received_on': json_format_datetime(form.received_on),
            'form_id': form.form_id,
            'case_ids': list(get_case_ids_from_form(form))
        })


class CaseRepeaterTest(BaseRepeaterTest, TestXmlMixin):
    domain = "case-rep"

    def setUp(self):
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url="case-repeater-url",
        )
        self.repeater = CaseRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='case_xml',
        )
        self.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super().tearDown()

    def test_case_close_format(self):
        # create a case
        submit_form_locally(self.xform_xml, self.domain)
        repeat_records = self.enqueued_repeat_records()
        payload = repeat_records[0].get_payload()
        self.assertXmlHasXpath(payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(payload, '//*[local-name()="create"]')

        # close the case
        CaseFactory(self.domain).close_case(CASE_ID)
        assert self.enqueued_repeat_records().count() == 1
        # Reload the repeat record because `payload_doc()` is memoized
        repeat_record = self.enqueued_repeat_records().first()
        close_payload = repeat_record.get_payload()
        self.assertXmlHasXpath(close_payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(close_payload, '//*[local-name()="close"]')

    def test_excluded_case_types_are_not_forwarded(self):
        self.repeater.white_listed_case_types = ['planet']
        self.repeater.save()

        white_listed_case = CaseBlock(
            case_id="a_case_id",
            create=True,
            case_type="planet",
        ).as_text()
        CaseFactory(self.domain).post_case_blocks([white_listed_case])
        self.assertEqual(1, len(self.enqueued_repeat_records()))

        non_white_listed_case = CaseBlock(
            case_id="b_case_id",
            create=True,
            case_type="cat",
        ).as_text()
        CaseFactory(self.domain).post_case_blocks([non_white_listed_case])
        self.assertEqual(1, len(self.enqueued_repeat_records()))

    def test_black_listed_user_cases_do_not_forward(self):
        self.repeater.black_listed_users = ['black_listed_user']
        self.repeater.save()
        black_list_user_id = 'black_listed_user'

        # case-creations by black-listed users shouldn't be forwarded
        black_listed_user_case = CaseBlock(
            case_id="aaa",
            create=True,
            case_type="planet",
            owner_id="owner",
            user_id=black_list_user_id
        ).as_text()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            black_list_user_id,
            '1234',
            black_listed_user_case,
        )
        submit_form_locally(xform_xml, self.domain)

        self.assertEqual(0, len(self.enqueued_repeat_records()))

        # case-creations by normal users should be forwarded
        normal_user_case = CaseBlock(
            case_id="bbb",
            create=True,
            case_type="planet",
            owner_id="owner",
            user_id="normal_user"
        ).as_text()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            '6789',
            normal_user_case,
        )
        submit_form_locally(xform_xml, self.domain)

        self.assertEqual(1, len(self.enqueued_repeat_records()))

        # case-updates by black-listed users shouldn't be forwarded
        black_listed_user_case = CaseBlock(
            case_id="ccc",
            case_type="planet",
            owner_id="owner",
            user_id=black_list_user_id,
        ).as_text()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            black_list_user_id,
            '2345',
            black_listed_user_case,
        )
        submit_form_locally(xform_xml, self.domain)
        self.assertEqual(1, len(self.enqueued_repeat_records()))

        # case-updates by normal users should be forwarded
        normal_user_case = CaseBlock(
            case_id="ddd",
            case_type="planet",
            owner_id="owner",
            user_id="normal_user",
        ).as_text()
        xform_xml = XFORM_XML_TEMPLATE.format(
            "https://www.commcarehq.org/test/repeater/",
            USER_ID,
            '3456',
            normal_user_case,
        )
        submit_form_locally(xform_xml, self.domain)
        self.assertEqual(2, len(self.enqueued_repeat_records()))

    def test_register_duplicate(self):
        factory = CaseFactory(self.domain)
        factory.post_case_blocks([
            CaseBlock(
                case_id='(134340) Pluto',
                create=True,
                case_name='Pluto',
                case_type='planet',
                date_opened='1930-02-18',
            ).as_text(),
        ])
        factory.post_case_blocks([
            CaseBlock(
                case_id='(134340) Pluto I',
                create=True,
                case_name='Charon',
                case_type='moon',
                date_opened='1978-06-22',
            ).as_text(),
        ])
        factory.post_case_blocks([
            CaseBlock(
                case_id='(134340) Pluto',
                update={
                    'case_type': 'dwarf_planet'
                },
                date_modified='2006-08-24',
            ).as_text(),
        ])
        repeat_records = self.repeater.repeat_records_ready.all()
        assert [r.payload_id for r in repeat_records] == [
            '(134340) Pluto',
            '(134340) Pluto I',
        ]


class RepeaterFailureTest(BaseRepeaterTest):
    domain = 'repeat-fail'

    def setUp(self):
        super().setUp()

        # Create the case before creating the repeater, so that the
        # repeater doesn't fire for the case creation. Each test
        # registers this case, and the repeater will fire then.
        submit_form_locally(self.xform_xml, self.domain)

        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater = CaseRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='case_json',
        )
        self.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super().tearDown()

    def test_payload_exception_on_fire(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        with patch('corehq.motech.repeaters.models.simple_request') as mock_simple_post:
            mock_simple_post.return_value.status_code = 503  # Fail and retry
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()
        with patch.object(CaseRepeater, 'get_payload', side_effect=Exception('Boom!')):
            state_or_none = rr.fire()

        self.assertIsNone(state_or_none)
        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.state, State.InvalidPayload)
        self.assertEqual(repeat_record.failure_reason, 'Boom!')

    def test_payload_exception_on_register(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        with patch.object(Repeater, "get_payload", side_effect=Exception('Payload error')):
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()

        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.state, State.InvalidPayload)
        self.assertEqual(repeat_record.failure_reason, "Payload error")

    def test_failure(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        with patch('corehq.motech.repeaters.models.simple_request', side_effect=RequestException('Boom!')):
            self.repeater.register(case)  # calls repeat_record.fire()
            rr = self.repeater.repeat_records.last()

        # Fetch the repeat_record revision that was updated
        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.failure_reason, 'Boom!')
        self.assertEqual(repeat_record.state, State.Fail)

    def test_unexpected_failure(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        with patch('corehq.motech.repeaters.models.simple_request', side_effect=Exception('Boom!')):
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()

        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.failure_reason, 'Internal Server Error')
        self.assertEqual(repeat_record.state, State.Fail)

    def test_success(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        # Should be marked as successful after a successful run
        with patch('corehq.motech.repeaters.models.simple_request') as mock_simple_post:
            mock_simple_post.return_value.status_code = 200
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()

        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.state, State.Success)

    def test_empty(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        # Should be marked as successful after a successful run
        with patch('corehq.motech.repeaters.models.simple_request') as mock_simple_post:
            mock_simple_post.return_value.status_code = 204
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()

        repeat_record = RepeatRecord.objects.get(id=rr.id)
        self.assertEqual(repeat_record.state, State.Empty)


class IgnoreDocumentTest(BaseRepeaterTest):
    domain = 'ignore-doc'

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
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='form-repeater-url',
        )
        self.repeater = FormRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='new_format',
        )
        self.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)

    def test_ignore_document(self):
        """
        When get_payload raises IgnoreDocument, fire should call update_success
        """
        repeat_records = RepeatRecord.objects.filter(domain=self.domain)
        for repeat_record_ in repeat_records:
            repeat_record_.fire()

            self.assertIsNone(repeat_record_.next_check)
            self.assertEqual(repeat_record_.state, State.Success)


class TestRepeaterFormat(BaseRepeaterTest):
    domain = 'test-fmt'

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
        super().setUp()
        submit_form_locally(self.xform_xml, self.domain)
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater = CaseRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='new_format',
        )
        self.repeater.save()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super().tearDown()

    def test_new_format_same_name(self):
        class NewCaseGenerator(BasePayloadGenerator):
            format_name = 'case_xml'
            format_label = 'XML'

            def get_payload(self, repeat_record, payload_doc):
                return {}

        with self.assertRaises(DuplicateFormatException):
            RegisterGenerator.get_collection(CaseRepeater).add_new_format(NewCaseGenerator)

    def test_new_format_second_default(self):
        class NewCaseGenerator(BasePayloadGenerator):
            format_name = 'rubbish'
            format_label = 'XML'

            def get_payload(self, repeat_record, payload_doc):
                return {}

        with self.assertRaises(DuplicateFormatException):
            RegisterGenerator.get_collection(CaseRepeater).add_new_format(NewCaseGenerator, is_default=True)

    def test_new_format_payload(self):
        case = CommCareCase.objects.get_case(CASE_ID, self.domain)
        with patch('corehq.motech.repeaters.models.simple_request') as mock_request, \
                patch.object(ConnectionSettings, 'get_auth_manager') as mock_manager:
            mock_request.return_value.status_code = 200
            mock_manager.return_value = 'MockAuthManager'
            self.repeater.register(case)
            rr = self.repeater.repeat_records.last()

            repeat_record = RepeatRecord.objects.get(id=rr.id)
            headers = self.repeater.get_headers(repeat_record)
            mock_request.assert_called_with(
                self.domain,
                self.connx.url,
                self.payload,
                auth_manager='MockAuthManager',
                headers=headers,
                notify_addresses=[],
                payload_id='ABC123CASEID',
                verify=self.repeater.verify,
                method="POST",
            )

    def test_get_format_by_deprecated_name(self):
        self.assertIsInstance(CaseRepeater(
            domain=self.domain,
            connection_settings=self.connx,
            format='new_format_alias',
        ).generator, self.new_generator)


class UserRepeaterTest(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'user-repeater'

        cls.domain_obj = create_domain(name=cls.domain)

        # DATA_FORWARDING is on PRO and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)

    def setUp(self):
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater = UserRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
        )
        self.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def enqueued_repeat_records(self):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)

    def make_user(self, username):
        user = CommCareUser.create(
            self.domain,
            "{}@{}.commcarehq.org".format(username, self.domain),
            "123",
            None,
            None,
        )
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        return user

    def test_trigger(self):
        self.assertEqual(0, len(self.enqueued_repeat_records()))
        user = self.make_user("bselmy")
        records = self.enqueued_repeat_records()
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
                'user_data': {'commcare_project': self.domain, 'commcare_profile': ''},
                'groups': [],
                'phone_numbers': [],
                'email': '',
                'eulas': '[]',
                'resource_uri': '/a/user-repeater/api/user/v1/{}/'.format(user._id),
                'locations': [],
                'primary_location': None,
            }
        )


class LocationRepeaterTest(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'loc-repeat'

        cls.domain_obj = create_domain(name=cls.domain)

        # DATA_FORWARDING is on PRO and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)

    def setUp(self):
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater = LocationRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
        )
        self.repeater.save()
        self.location_type = LocationType.objects.create(
            domain=self.domain,
            name="city",
        )

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def enqueued_repeat_records(self):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)

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
        self.assertEqual(0, len(self.enqueued_repeat_records()))
        location = self.make_location('kings_landing')
        records = self.enqueued_repeat_records()
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
                'archived_on': None,
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
    domain = 'rep-pause'

    def setUp(self):
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater = FormRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='form_xml',
        )
        self.repeater.save()
        submit_form_locally(self.xform_xml, self.domain)
        self.repeater = Repeater.objects.get(id=self.repeater.id)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(TestRepeaterPause, self).tearDown()

    def test_trigger_when_paused(self):
        # not paused
        with (
            patch.object(RepeatRecord, 'fire') as mock_fire,
            patch.object(RepeatRecord, 'postpone_by') as mock_postpone_fire
        ):
            repeat_record = RepeatRecord.objects.get(payload_id=self.instance_id)
            _process_repeat_record(repeat_record)
            self.assertEqual(mock_fire.call_count, 1)
            self.assertEqual(mock_postpone_fire.call_count, 0)

            # paused
            self.repeater.pause()
            # re fetch repeat record
            repeat_record = RepeatRecord.objects.get(payload_id=self.instance_id)
            _process_repeat_record(repeat_record)
            self.assertEqual(mock_fire.call_count, 1)
            self.assertEqual(mock_postpone_fire.call_count, 1)

            # resumed
            self.repeater.resume()
            # re fetch repeat record
            repeat_record = RepeatRecord.objects.get(payload_id=self.instance_id)
            _process_repeat_record(repeat_record)
            self.assertEqual(mock_fire.call_count, 2)
            self.assertEqual(mock_postpone_fire.call_count, 1)


class TestRepeaterDeleted(BaseRepeaterTest):
    domain = 'rep-deleted'

    def setUp(self):
        super().setUp()
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater = FormRepeater(
            domain=self.domain,
            connection_settings_id=self.connx.id,
            format='form_xml',
        )
        self.repeater.save()
        submit_form_locally(self.xform_xml, self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super().tearDown()

    def test_trigger_when_deleted(self):
        self.repeater.retire()

        with patch.object(RepeatRecord, 'fire') as mock_fire:
            repeat_record = RepeatRecord.objects.get(payload_id=self.instance_id)
            _process_repeat_record(repeat_record)
            self.assertEqual(mock_fire.call_count, 0)
            self.assertEqual(repeat_record.state, State.Cancelled)


@attr.s
class Response(object):
    status_code = attr.ib()
    reason = attr.ib()
    content = attr.ib(default=None)
    encoding = attr.ib(default='ascii')

    @property
    def text(self):
        return '' if self.content is None else self.content.decode(self.encoding, errors='replace')


class DummyRepeater(Repeater):

    class Meta:
        proxy = True

    @property
    def generator(self):
        return FormRepeaterXMLPayloadGenerator(self)

    def payload_doc(self, repeat_record):
        return {}


class HandleResponseTests(SimpleTestCase):
    domain = 'handle-resp'

    def setUp(self):
        self.repeater = DummyRepeater(
            domain=self.domain,
            connection_settings_id=1,

        )
        self.repeat_record = Mock()

    def test_handle_ok_response(self):
        response = Response(status_code=200, reason='OK', content=b'OK')
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_called()
        self.repeat_record.handle_server_failure.assert_not_called()

    def test_handle_true_response(self):
        response = True
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_called()
        self.repeat_record.handle_server_failure.assert_not_called()

    def test_handle_none_response(self):
        response = None
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_server_failure.assert_called()

    def test_handle_bad_gateway_response(self):
        response = Response(status_code=502, reason='The core is exposed')
        self.repeater.handle_response(response, self.repeat_record)

        self.repeat_record.handle_exception.assert_not_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_server_failure.assert_called()

    def test_handle_exception(self):
        err = Exception('The core is exposed')
        self.repeater.handle_response(err, self.repeat_record)

        self.repeat_record.handle_exception.assert_called()
        self.repeat_record.handle_success.assert_not_called()
        self.repeat_record.handle_server_failure.assert_not_called()


class FormatResponseTests(SimpleTestCase):

    def test_content_is_ascii(self):
        response = Response(
            status_code=200,
            reason='OK',
            content=b'3.6 roentgen. Not great. Not terrible.'
        )
        formatted = format_response(response)
        self.assertEqual(formatted, '200: OK\n3.6 roentgen. Not great. Not terrible.')

    def test_encoding_is_not_ascii(self):
        response = Response(
            status_code=200,
            reason='OK',
            content=b'3,6 \xe1\xa8\xd4\xe5\xac\xa8\xd4\xa0 \xd5\xa8 \xb5\xd6\xe1\xd6\xf5\xd6. '
                    b'\xd5\xa8 \xe3\xe5\xe1\xa0\xf5\xd4\xd6',
            encoding='cp855'
        )
        formatted = format_response(response)
        self.assertEqual(formatted, '200: OK\n3,6 рентгена Не хорошо. Не страшно')

    def test_content_is_None(self):
        response = Response(500, 'The core is exposed')
        formatted = format_response(response)
        self.assertEqual(formatted, '500: The core is exposed')


class TestGetRetryInterval(SimpleTestCase):

    def test_no_last_checked(self):
        last_checked = None
        now = fromisoformat("2020-01-01 00:05:00")
        interval = _get_retry_interval(last_checked, now)
        self.assertEqual(interval, MIN_RETRY_WAIT)

    def test_min_interval(self):
        last_checked = fromisoformat("2020-01-01 00:00:00")
        now = fromisoformat("2020-01-01 00:05:00")
        interval = _get_retry_interval(last_checked, now)
        self.assertEqual(interval, MIN_RETRY_WAIT)

    def test_max_interval(self):
        last_checked = fromisoformat("2020-01-01 00:00:00")
        now = fromisoformat("2020-02-01 00:00:00")
        interval = _get_retry_interval(last_checked, now)
        self.assertEqual(interval, MAX_RETRY_WAIT)

    def test_three_times_interval(self):
        last_checked = fromisoformat("2020-01-01 00:00:00")
        now = fromisoformat("2020-01-01 01:00:00")
        interval = _get_retry_interval(last_checked, now)
        self.assertEqual(interval, timedelta(hours=3))

    def test_five_retries(self):
        # (Five retries because RepeatRecord.max_possible_tries is 6)
        for last_checked, now, expected_interval_hours in [
            (None, fromisoformat("2020-01-01 00:00:00"), 1),
            (fromisoformat("2020-01-01 00:00:00"), fromisoformat("2020-01-01 01:00:00"), 3),
            (fromisoformat("2020-01-01 01:00:00"), fromisoformat("2020-01-01 04:00:00"), 9),
            (fromisoformat("2020-01-01 04:00:00"), fromisoformat("2020-01-01 13:00:00"), 27),
            (fromisoformat("2020-01-01 13:00:00"), fromisoformat("2020-01-02 16:00:00"), 81),
        ]:
            interval = _get_retry_interval(last_checked, now)
            self.assertEqual(interval, timedelta(hours=expected_interval_hours))


class DataSourceRepeaterTest(BaseRepeaterTest):
    domain = "user-reports"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source = get_sample_data_source()
        cls.data_source.save()
        cls.addClassCleanup(cls.data_source.delete)
        cls.adapter = get_indicator_adapter(cls.data_source)
        cls.adapter.build_table()
        cls.addClassCleanup(cls.adapter.drop_table)
        cls.pillow = _get_pillow([cls.data_source], processor_chunk_size=100)

        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url="case-repeater-url",
        )
        cls.data_source_id = cls.data_source._id
        cls.repeater = DataSourceRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
            data_source_id=cls.data_source_id,
        )
        cls.repeater.save()

    def test_datasource_is_subscribed_to(self):
        assert self.repeater.datasource_is_subscribed_to(
            self.domain,
            self.data_source_id,
        )
        assert self.repeater.datasource_is_subscribed_to(
            "malicious-domain",
            self.data_source_id
        ) is False

    @flag_enabled('SUPERSET_ANALYTICS')
    def test_payload(self):
        doc_id, expected_indicators = self._create_payload()
        datasource_update = DataSourceUpdate.objects.first()
        assert datasource_update.data_source_id.hex == self.data_source_id
        assert datasource_update.doc_ids == [doc_id]

    @flag_enabled('SUPERSET_ANALYTICS')
    def test_payload_format(self):
        doc_id, expected_indicators = self._create_payload()
        repeat_record = self.repeater.repeat_records_ready.first()
        payload_str = repeat_record.get_payload()
        payload = json.loads(payload_str)

        # assert payload == {
        #     'data_source_id': self.data_source._id,
        #     'doc_id': '',
        #     'doc_ids': [doc_id],
        #     'data': [expected_indicators],
        # }
        # ^^^ kinda like this, but accommodates the value of "estimate":
        assert set(payload.keys()) == {'data_source_id', 'doc_id', 'doc_ids', 'data'}
        assert payload['data_source_id'] == self.data_source._id
        assert payload['doc_id'] == ''
        assert payload['doc_ids'] == [doc_id]
        assert len(payload['data']) == 1
        for key, value in payload['data'][0].items():
            if key == 'estimate':
                # '2.3000000000000000' == '2.2999999999...1893310546875'
                assert float(value) == float(expected_indicators[key])
            else:
                assert value == expected_indicators[key]

    def _create_payload(self):
        from corehq.apps.userreports.tests.test_pillow import _save_sql_case

        with patch('corehq.apps.userreports.specs.datetime') as datetime_mock:
            fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
            datetime_mock.utcnow.return_value = fake_time_now
            sample_doc, expected_indicators = get_sample_doc_and_indicators(fake_time_now)
            since = self.pillow.get_change_feed().get_latest_offsets()
            _save_sql_case(sample_doc)
            self.pillow.process_changes(since=since, forever=False)

        # Serialize and deserialize to get objects as strings
        json_indicators = json.dumps(expected_indicators, cls=CommCareJSONEncoder)
        expected_indicators = json.loads(json_indicators)
        return sample_doc['_id'], expected_indicators


class TestSetBackoff(TestCase):
    domain = 'test-race-condition'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url='https://example.com/api/',
        )
        cls.repeater = CaseRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
            format='case_json',
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.repeater.delete()
        cls.connx.delete()
        super().tearDownClass()

    def test_race_condition(self):
        repeater_a = Repeater.objects.get(id=self.repeater.repeater_id)
        repeater_b = Repeater.objects.get(id=self.repeater.repeater_id)
        self.assertIsNone(repeater_a.next_attempt_at)
        self.assertFalse(repeater_b.is_paused)

        repeater_a.set_backoff()
        repeater_b.pause()

        repeater_c = Repeater.objects.get(id=self.repeater.repeater_id)
        self.assertIsNotNone(repeater_c.next_attempt_at)
        self.assertTrue(repeater_c.is_paused)

    def test_initial_get_next_attempt_at(self):
        next_attempt_at = self.repeater._get_next_attempt_at(None)
        in_5_mins = datetime.utcnow() + MIN_REPEATER_RETRY_WAIT
        self.assertEqual(
            next_attempt_at.isoformat(timespec='seconds'),
            in_5_mins.isoformat(timespec='seconds')
        )

    def test_get_next_attempt_at(self):
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        next_attempt_at = self.repeater._get_next_attempt_at(five_mins_ago)
        # Double the last interval
        in_10_mins = datetime.utcnow() + timedelta(minutes=10)
        self.assertEqual(
            next_attempt_at.isoformat(timespec='seconds'),
            in_10_mins.isoformat(timespec='seconds')
        )

    def test_max_get_next_attempt_at(self):
        last_month = datetime(2020, 1, 1, 0, 0, 0)
        next_attempt_at = self.repeater._get_next_attempt_at(last_month)
        in_7_days = datetime.utcnow() + MAX_RETRY_WAIT
        self.assertEqual(
            next_attempt_at.isoformat(timespec='seconds'),
            in_7_days.isoformat(timespec='seconds')
        )

    def test_reset_on_pause(self):
        self.repeater.set_backoff()
        self.repeater.pause()
        repeater = Repeater.objects.get(id=self.repeater.repeater_id)
        assert repeater.next_attempt_at is None


def fromisoformat(isoformat):
    """
    Return a datetime from a string in ISO 8601 date time format

    >>> fromisoformat("2019-12-31 23:59:59")
    datetime.datetime(2019, 12, 31, 23, 59, 59)

    """
    try:
        return datetime.fromisoformat(isoformat)  # Python >= 3.7
    except AttributeError:
        return datetime.strptime(isoformat, "%Y-%m-%d %H:%M:%S")


def _get_pillow(configs, processor_chunk_size=0):
    pillow = get_case_pillow(processor_chunk_size=processor_chunk_size)
    # overwrite processors since we're only concerned with UCR here
    table_manager = ConfigurableReportTableManager(data_source_providers=[])
    ucr_processor = ConfigurableReportPillowProcessor(
        table_manager
    )
    table_manager.bootstrap(configs)
    pillow.processors = [ucr_processor]
    return pillow
