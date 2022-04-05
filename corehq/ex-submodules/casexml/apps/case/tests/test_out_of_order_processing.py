import os
from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import softer_assert


class OutOfOrderCaseTest(TestCase):

    def setUp(self):
        super(OutOfOrderCaseTest, self).setUp()
        delete_all_cases()

    @softer_assert()
    def testOutOfOrderSubmissions(self):
        dir = os.path.join(os.path.dirname(__file__), "data", "ordering")
        for fname in ('update_oo.xml', 'create_oo.xml'):
            with open(os.path.join(dir, fname), "rb") as f:
                xml_data = f.read()
            submit_form_locally(xml_data, 'test-domain')

        case = CommCareCase.objects.get_case('30bc51f6-3247-4966-b4ae-994f572e85fe', 'test-domain')
        self.assertEqual('from the update form', case.case_json['pupdate'])
        self.assertEqual('from the create form', case.case_json['pcreate'])
        # NOTE the SQL form processor works differently than the Couch one did:
        # it processes submissions in the order they are received
        self.assertEqual('this should get overridden', case.case_json['pboth'])
