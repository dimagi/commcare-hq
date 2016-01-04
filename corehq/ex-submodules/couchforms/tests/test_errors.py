from django.test import TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.tests.utils import run_with_all_backends


class CaseProcessingErrorsTest(TestCase):

    @run_with_all_backends
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

        domain = 'special_domain'
        _, xform, _ = submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-123</instanceID>
                </meta>
            <case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
                <update><foo>bar</foo></update>
            </case>
            </data>""",
            domain,
        )
        self.assertTrue(xform.is_error)
        self.assertEqual(xform.problem, 'IllegalCaseId: case_id must not be empty')

    @run_with_all_backends
    def test_uses_referrals(self):
        """
        submit form with a case block that uses referrals

        check that
        - it errors
        - the form is not saved under its original id
        - an XFormError is saved with the original id as orig_id
        """
        domain = 'special_domain'
        _, xform, _ = submit_form_locally(
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
            domain,
        )
        self.assertTrue(xform.is_error)
        self.assertEqual(xform.problem, 'UsesReferrals: Sorry, referrals are no longer supported!')
