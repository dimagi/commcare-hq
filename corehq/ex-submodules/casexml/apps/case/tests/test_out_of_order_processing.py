import os
from django.test.utils import override_settings
from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_cases
from corehq.form_processor.interfaces import FormProcessorInterface


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OutOfOrderCaseTest(TestCase):

    def setUp(self):
        delete_all_cases()

    def testOutOfOrderSubmissions(self):
        dir = os.path.join(os.path.dirname(__file__), "data", "ordering")
        forms = []
        for fname in ('create_oo.xml', 'update_oo.xml'):
            with open(os.path.join(dir, fname), "rb") as f:
                xml_data = f.read()
            forms.append(FormProcessorInterface.post_xform(xml_data))

        [create, update] = forms

        # process out of order
        FormProcessorInterface.process_cases(update)
        FormProcessorInterface.process_cases(create)

        case = FormProcessorInterface.get_case('30bc51f6-3247-4966-b4ae-994f572e85fe')
        self.assertEqual('from the update form', case.pupdate)
        self.assertEqual('from the create form', case.pcreate)
        self.assertEqual('overridden by the update form', case.pboth)
