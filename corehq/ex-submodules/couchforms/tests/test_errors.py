from django.test import TestCase
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormError


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
        xform_errors = XFormError.view(
            'domain/docs',
            startkey=['my_very_special_domain', 'XFormError'],
            endkey=['my_very_special_domain', 'XFormError', {}],
            reduce=False,
            include_docs=True,
        ).all()

        related_errors = [xform_error for xform_error in xform_errors
                          if xform_error.get_id == 'abc-easy-as-123']
        self.assertEqual(len(related_errors), 1)
        related_error = related_errors[0]
        self.assertEqual(related_error.problem,
                         'IllegalCaseId: case_id must not be empty')
