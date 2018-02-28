from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.hqcase.utils import update_case
from corehq.apps.reminders.models import CaseReminder, CaseReminderHandler
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.enikshay.messaging.custom_content import prescription_voucher_alert
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from django.test import TestCase, override_settings


class FakeRecipient(object):

    def __init__(self, language_code):
        self.language_code = language_code

    def get_language_code(self):
        return self.language_code


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ENikshayCustomContentTest(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(ENikshayCustomContentTest, self).setUp()
        self.create_case_structure()

    def tearDown(self):
        super(ENikshayCustomContentTest, self).tearDown()
        FormProcessorTestUtils.delete_all_cases(domain=self.domain)

    def test_prescription_voucher_alert_default_language(self):
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        update_case(self.domain, voucher.case_id, {'voucher_id': '012345'})
        update_case(self.domain, self.person_id, {'name': 'Joe', 'person_id': '123-456-789'})

        self.assertEqual(
            prescription_voucher_alert(
                CaseReminder(case_id=voucher.case_id),
                CaseReminderHandler(default_lang='en'),
                FakeRecipient(None)
            ),
            "Drug Voucher ID 012345 issued to Joe with Beneficiary ID 123-456-789."
        )

    def test_prescription_voucher_alert_translation(self):
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        update_case(self.domain, voucher.case_id, {'voucher_id': '012345'})
        update_case(self.domain, self.person_id, {'name': 'Joe', 'person_id': '123-456-789'})

        self.assertEqual(
            prescription_voucher_alert(
                CaseReminder(case_id=voucher.case_id),
                CaseReminderHandler(default_lang='en'),
                FakeRecipient('hin')
            ),
            ("\u0926\u0935\u093e \u0935\u093e\u0909\u091a\u0930 \u0906\u0908\u0921\u0940 012345"
             " \u0932\u093e\u092d\u093e\u0930\u094d\u0925\u0940 \u0906\u0908\u0921\u0940 123-456-789"
             "  \u0915\u0947 \u0938\u093e\u0925 Joe \u0915\u094b \u091c\u093e\u0930\u0940 "
             "\u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964")
        )
