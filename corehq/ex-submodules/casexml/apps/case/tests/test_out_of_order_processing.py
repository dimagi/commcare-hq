import os
from django.test.utils import override_settings
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import process_cases
from casexml.apps.case.tests.util import post_util as real_post_util, delete_all_cases
from couchforms.tests.testutils import post_xform_to_couch


def post_util(**kwargs):
    form_extras = kwargs.get('form_extras', {})
    form_extras['domain'] = 'out-of-order-test'
    kwargs['form_extras'] = form_extras
    return real_post_util(**kwargs)


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
            forms.append(post_xform_to_couch(xml_data))

        [create, update] = forms

        # process out of order
        process_cases(update)
        process_cases(create)

        case = CommCareCase.get('30bc51f6-3247-4966-b4ae-994f572e85fe')
        self.assertEqual('from the update form', case.pupdate)
        self.assertEqual('from the create form', case.pcreate)
        self.assertEqual('overridden by the update form', case.pboth)
