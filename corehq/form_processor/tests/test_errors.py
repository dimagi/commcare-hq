from django.test import TestCase
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormError

from ..interfaces import FormProcessorInterface


class CaseProcessingErrorsTest(TestCase):

    def test_no_case_id(self):
        """
        submit form with a case block that has no case_id

        check that
        - it errors
        - the form is not saved under its original id
        - an XFormError is saved with the original id as orig_id
        - the error was logged (<-- is this hard to test?)

        <data xmlns="example.com/foo">
            <case case_id="">
                <update><foo>bar</foo></update>
            </case>
        </data>
        """
        submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-123</instanceID>
                </meta>
            <case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
                <update><foo>bar</foo></update>
            </case>
            </data>""",
            'my_very_special_domain',
        )
        xform_errors = FormProcessorInterface.get_by_doc_type('my_very_special_domain', 'XFormError')

        related_errors = [xform_error for xform_error in xform_errors
                          if xform_error.to_generic().id == 'abc-easy-as-123']
        self.assertEqual(len(related_errors), 1)
        related_error = related_errors[0]
        self.assertEqual(related_error.to_generic().problem,
                         'IllegalCaseId: case_id must not be empty')

    def test_uses_referrals(self):
        """
        submit form with a case block that uses referrals

        check that
        - it errors
        - the form is not saved under its original id
        - an XFormError is saved with the original id as orig_id
        """
        submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-456</instanceID>
                </meta>
            <case case_id="123" xmlns="http://commcarehq.org/case/transaction/v2">
                <referral>
                    <referral_id>456</referral_id>
                    <open>
                        <referral_types>t1 t2</referral_types>
                    </open>
                </referral>
            </case>
            </data>""",
            'my_very_special_domain',
        )
        xform_errors = FormProcessorInterface.get_by_doc_type('my_very_special_domain', 'XFormError')

        related_errors = [xform_error for xform_error in xform_errors
                          if xform_error.to_generic().id == 'abc-easy-as-456']
        self.assertEqual(len(related_errors), 1)
        related_error = related_errors[0]
        self.assertEqual(related_error.to_generic().problem,
                'UsesReferrals: Sorry, referrals are no longer supported!')
