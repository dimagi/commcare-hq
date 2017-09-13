import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.apps.zapier.consts import EventTypes
from corehq.apps.zapier.models import ZapierSubscription
from corehq.apps.zapier.tests.test_utils import bootrap_domain_for_zapier, cleanup_repeaters_for_domain, \
    cleanup_repeat_records_for_domain
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.motech.repeaters.models import RepeatRecord


DOMAIN = 'zapier-case-forwarding-tests'


class TestZapierCaseForwarding(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierCaseForwarding, cls).setUpClass()
        from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
        delete_all_users()
        cls.domain = DOMAIN
        cls.domain_object, cls.web_user, cls.api_key = bootrap_domain_for_zapier(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete()
        cls.domain_object.delete()
        cleanup_repeaters_for_domain(cls.domain)
        super(TestZapierCaseForwarding, cls).tearDownClass()

    def tearDown(self):
        cleanup_repeat_records_for_domain(self.domain)
        ZapierSubscription.objects.all().delete()

    @run_with_all_backends
    def test_create_case_forwarding(self):
        subscription = ZapierSubscription.objects.create(
            domain=self.domain,
            user_id=str(self.web_user._id),
            event_name=EventTypes.NEW_CASE,
            url='http://example.com/lets-make-some-cases/',
            case_type='animal',
        )

        # creating a case should trigger the repeater
        case_id = uuid.uuid4().hex
        post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_type='animal',
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(1, len(repeat_records))
        record = repeat_records[0]
        self.assertEqual(case_id, record.payload_id)

        # updating a case should not
        post_case_blocks(
            [
                CaseBlock(
                    create=False,
                    case_id=case_id,
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(1, len(repeat_records))

    @run_with_all_backends
    def test_update_case_forwarding(self):
        subscription = ZapierSubscription.objects.create(
            domain=self.domain,
            user_id=str(self.web_user._id),
            event_name=EventTypes.UPDATE_CASE,
            url='http://example.com/lets-make-some-cases/',
            case_type='animal',
        )

        # creating a case should NOT trigger the repeater
        case_id = uuid.uuid4().hex
        post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_type='animal',
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(0, len(repeat_records))

        # updating a case should
        post_case_blocks(
            [
                CaseBlock(
                    create=False,
                    case_id=case_id,
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(1, len(repeat_records))
        record = repeat_records[0]
        self.assertEqual(case_id, record.payload_id)

    @run_with_all_backends
    def test_changed_case_forwarding(self):
        subscription = ZapierSubscription.objects.create(
            domain=self.domain,
            user_id=str(self.web_user._id),
            event_name=EventTypes.CHANGED_CASE,
            url='http://example.com/lets-make-some-cases/',
            case_type='animal',
        )

        # creating a case should NOT trigger the repeater
        case_id = uuid.uuid4().hex
        post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_type='animal',
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(1, len(repeat_records))
        record = repeat_records[0]
        self.assertEqual(case_id, record.payload_id)

        # updating a case should
        post_case_blocks(
            [
                CaseBlock(
                    create=False,
                    case_id=case_id,
                ).as_xml()
            ], domain=self.domain
        )
        repeat_records = list(RepeatRecord.all(domain=self.domain))
        self.assertEqual(2, len(repeat_records))
        for record in repeat_records:
            self.assertEqual(case_id, record.payload_id)
