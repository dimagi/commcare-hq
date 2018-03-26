from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree
from django.test import TestCase

from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.case.xform import process_cases_with_casedb
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.tests.utils import use_sql_backend


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
        super(StrictDatetimesTest, cls).setUpClass()
        cls.domain = 'strict-datetimes-test-domain'
        cls.interface = FormProcessorInterface(cls.domain)

    def test(self):
        form = _make_form_from_case_blocks([ElementTree.fromstring(CASE_BLOCK)])
        result = process_xform_xml(self.domain, form)
        with result.get_locked_forms() as xforms:
            with self.interface.casedb_cache(domain=self.domain) as case_db:
                with self.assertRaises(PhoneDateValueError):
                    process_cases_with_casedb(xforms, case_db)


@use_sql_backend
class StrictDatetimesTestSQL(StrictDatetimesTest):
    pass


def _make_form_from_case_blocks(case_blocks):
    form = ElementTree.Element("data")
    form.attrib['xmlns'] = "https://www.commcarehq.org/test/casexml-wrapper"
    form.attrib['xmlns:jrm'] = "http://openrosa.org/jr/xforms"
    for block in case_blocks:
        form.append(block)
    return ElementTree.tostring(form)
