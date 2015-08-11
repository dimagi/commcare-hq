from xml.etree import ElementTree
from django.test import TestCase
from casexml.apps.case.util import make_form_from_case_blocks
from casexml.apps.case.xform import process_cases_with_casedb, CaseDbCache
from couchforms.exceptions import PhoneDateValueError
from couchforms.util import process_xform


CASE_ID = 'a0cd5e6c5fb84695a4f729d3b1996a93'
# the bad date in date_modified is what we're interested in
CASE_BLOCK = """
<n0:case case_id="{case_id}"
         date_modified="2015-08-06T14:33:12.077 05:30"
         user_id="d37bf37ee0ff4ec4a8aa114baa046a25"
         xmlns:n0="http://commcarehq.org/case/transaction/v2">
    <n0:create>
        <n0:case_name>Forple Snord</n0:case_name>
        <n0:owner_id>d37bf37ee0ff4ec4a8aa114baa046a25</n0:owner_id>
        <n0:case_type>footron</n0:case_type>
    </n0:create>
</n0:case>
""".format(case_id=CASE_ID)


class StrictDatetimesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'strict-datetimes-test-domain'

    def test(self):
        form = make_form_from_case_blocks([ElementTree.fromstring(CASE_BLOCK)])
        lock_manager = process_xform(form, domain=self.domain)
        with lock_manager as xforms:
            with CaseDbCache(domain=self.domain) as case_db:
                with self.assertRaises(PhoneDateValueError):
                    process_cases_with_casedb(xforms, case_db)
