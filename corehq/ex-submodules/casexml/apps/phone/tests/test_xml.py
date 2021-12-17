import datetime
import os.path
from django.test import SimpleTestCase

import casexml.apps.phone.xml as xml

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.form_processor.models import CommCareCaseSQL


class TestCaseDBElement(TestXmlMixin, SimpleTestCase):
    root = os.path.dirname(__file__)
    file_path = ['data']

    domain = 'winterfell'

    def create_case(self):
        return CommCareCaseSQL(
            case_id='redwoman',
            domain=self.domain,
            opened_on=datetime.datetime(2016, 5, 31),
            modified_on=datetime.datetime(2016, 5, 31),
            type='priestess',
            closed=False,
            name='melisandre',
            owner_id='lordoflight',
            indices=[dict(
                identifier='advisor',
                referenced_type='human',
                referenced_id='stannis',
                relationship='extension',
            )],
            case_json=dict(
                power='prophecy',
                hometown='asshai',
            ),
        )

    def test_generate_xml(self):
        case = self.create_case()
        case_xml = xml.tostring(xml.get_casedb_element(case))
        self.assertXmlEqual(self.get_xml('case_db_block'), case_xml)
