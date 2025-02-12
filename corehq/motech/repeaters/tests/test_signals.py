from uuid import uuid4

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import RepeatRecord, UpdateCaseRepeater
from corehq.util.test_utils import create_and_save_a_case

DOMAIN = 'test-domain'

XFORM_XML_TEMPLATE = """<?xml version='1.0' ?>
<data xmlns="https://www.commcarehq.org/test/repeater/"
      xmlns:jrm="http://dev.commcarehq.org/jr/xforms">
  <case_name>Gulf of America</case_name>
  <meta>
    <deviceID>O2XLT0WZW97W1A91E2W1Y0NJG</deviceID>
    <timeStart>2025-02-12T21:59:37.650810Z</timeStart>
    <timeEnd>2025-02-12T21:59:37.650810Z</timeEnd>
    <username>admin</username>
    <userID>admin@test.example.com</userID>
    <instanceID>{instance_id}</instanceID>
  </meta>
  <case case_id="{case_id}"
        date_modified="2025-02-12T21:59:37.650810Z"
        xmlns="http://commcarehq.org/case/transaction/v2">
    <update>
      <case_name>Gulf of America</case_name>
    </update>
  </case>
</data>
"""


class TestCreateRepeatRecords(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(domain_obj.delete)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)
        cls.addClassCleanup(cls.teardown_subscriptions)

    def setUp(self):
        connx = ConnectionSettings.objects.create(
            domain=DOMAIN,
            url='https://example.com/api/',
        )
        self.repeater = UpdateCaseRepeater(
            domain=DOMAIN,
            connection_settings_id=connx.id,
        )
        self.repeater.save()

        deleted_repeater = UpdateCaseRepeater(
            domain=DOMAIN,
            connection_settings_id=connx.id,
        )
        deleted_repeater.save()
        deleted_repeater.delete()

    def test_deleted_repeater_records(self):
        # Verifies that `create_repeat_records(UpdateCaseRepeater, case)`
        # in signals.py does not create a repeat record for a deleted
        # repeater.
        case_id = uuid4().hex
        create_and_save_a_case(DOMAIN, case_id, 'Gulf of Mexico')
        update_xform_xml = XFORM_XML_TEMPLATE.format(
            instance_id=uuid4().hex,
            case_id=case_id,
        )
        # Calls create_repeat_records(UpdateCaseRepeater, case):
        submit_form_locally(update_xform_xml, DOMAIN)

        assert RepeatRecord.objects.count() == 1
        repeat_record = RepeatRecord.objects.first()
        assert repeat_record.repeater == self.repeater
