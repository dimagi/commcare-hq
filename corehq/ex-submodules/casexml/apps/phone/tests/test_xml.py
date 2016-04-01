import datetime

import os.path
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.xml import get_casedb_xml
from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin


class TestCaseDBElement(TestXmlMixin, SimpleTestCase):
    root = os.path.dirname(__file__)
    file_path = ['data']

    domain = 'winterfell'

    def setUp(self):
        self.case = CommCareCase(
            domain=self.domain,
            opened_on=datetime.datetime(2016, 5, 31),
            modified_on=datetime.datetime(2016, 5, 31),
            type='priestess',
            closed=False,
            name='melisandre',
            owner_id='lordoflight',
            indices=[CommCareCaseIndex(
                identifier='advisor',
                referenced_type='human',
                referenced_id='stannis',
                relationship='extension',
            )]
        )
        self.case._id = 'redwoman'
        self.case.power = 'prophecy'
        self.case.hometown = 'asshai'

    def test_generate_xml(self):
        self.assertXmlEqual(get_casedb_xml(self.case), self.get_xml('case_db_block'))
