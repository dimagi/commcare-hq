from django.test import TestCase
import os
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import sharded

TEST_DOMAIN = 'test-domain'


@sharded
class CaseExclusionTest(TestCase):
    """
    Tests the exclusion of device logs from case processing
    """

    def setUp(self):
        super(CaseExclusionTest, self).setUp()
        delete_all_cases()

    def testTopLevelExclusion(self):
        """
        Entire forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        submit_form_locally(xml_data, TEST_DOMAIN)
        self.assertEqual(0, len(CommCareCase.objects.get_case_ids_in_domain(TEST_DOMAIN)))

    def testNestedExclusion(self):
        """
        Blocks inside forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "nested_device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        result = submit_form_locally(xml_data, TEST_DOMAIN)
        self.assertEqual(['case_in_form'], CommCareCase.objects.get_case_ids_in_domain(TEST_DOMAIN))
        self.assertEqual("form case", result.case.name)
