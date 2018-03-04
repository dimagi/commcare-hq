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

    def _test_prescription_voucher_alert_with_language(self, voucher, language_code, expected_message):
        self.assertEqual(
            prescription_voucher_alert(
                CaseReminder(case_id=voucher.case_id),
                CaseReminderHandler(default_lang='en'),
                FakeRecipient(language_code)
            ),
            expected_message
        )

    def test_prescription_voucher_alert(self):
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        update_case(self.domain, voucher.case_id, {'voucher_id': '012345'})
        update_case(self.domain, self.person_id, {'name': 'Joe', 'person_id': '123-456-789'})

        self._test_prescription_voucher_alert_with_language(
            voucher,
            None,
            "Drug Voucher ID 012345 issued to Joe with Beneficiary ID 123-456-789."
        )
        self._test_prescription_voucher_alert_with_language(
            voucher,
            "en",
            "Drug Voucher ID 012345 issued to Joe with Beneficiary ID 123-456-789."
        )
        self._test_prescription_voucher_alert_with_language(
            voucher,
            "bho",
            "\u0921\u094d\u0930\u0917 \u0935\u093e\u0909\u091a\u0930 \u0906\u0908\u0921\u0940 012345"
            " \u092f\u0947 \u0932\u093e\u092d\u093e\u0930\u094d\u0925\u0940 \u0906\u0908\u0921\u0940 "
            "123-456-789  \u0915\u0947 \u0938\u0902\u0917\u0947 Joe \u0915\u0947 \u091c\u093e\u0930\u0940 "
            "\u0915 \u0926\u0947\u0939\u0932 \u0917\u0908\u0932 \u092c\u093e"
        )
        self._test_prescription_voucher_alert_with_language(
            voucher,
            "guj",
            "\u0ab2\u0abe\u0aad\u0abe\u0ab0\u0acd\u0aa5\u0ac0 \u0a86\u0a88\u0aa1\u0ac0  123-456-789"
            "  \u0aa7\u0ab0\u0abe\u0ab5\u0aa4\u0abe Joe \u0aa8\u0ac7 \u0aa1\u0acd\u0ab0\u0a97 "
            "\u0ab5\u0abe\u0a89\u0a9a\u0ab0 \u0a86\u0a88\u0aa1\u0ac0   012345 \u0a88\u0ab6\u0acd\u0aaf\u0ac1 "
            "\u0a95\u0ab0\u0ab5\u0abe\u0aae\u0abe\u0a82 \u0a86\u0ab5\u0acd\u0aaf\u0ac1\u0a82 \u0a9b\u0ac7."
        )
        self._test_prescription_voucher_alert_with_language(
            voucher,
            "hin",
            "\u0926\u0935\u093e \u0935\u093e\u0909\u091a\u0930 \u0906\u0908\u0921\u0940 012345"
            " \u0932\u093e\u092d\u093e\u0930\u094d\u0925\u0940 \u0906\u0908\u0921\u0940 123-456-789  "
            "\u0915\u0947 \u0938\u093e\u0925 Joe \u0915\u094b \u091c\u093e\u0930\u0940 \u0915\u093f\u092f\u093e "
            "\u0917\u092f\u093e \u0939\u0948\u0964"
        )
        self._test_prescription_voucher_alert_with_language(
            voucher,
            "mar",
            "123-456-789 \u0939\u093e \u0932\u093e\u092d\u0927\u093e\u0930\u0915\u0906\u092f\u0921\u0940 "
            "\u0905\u0938\u0932\u0947\u0932\u094d\u092f\u093e Joe \u0935\u094d\u092f\u0915\u094d\u0924\u0940"
            "\u0932\u093e\u0921\u094d\u0930\u0917\u0935\u094d\u0939\u093e\u090a\u091a\u0930\u0906\u092f\u0921"
            "\u0940 012345 \u0926\u0947\u0923\u094d\u092f\u093e\u0924 \u0906\u0932\u093e \u0906\u0939\u0947."
        )
