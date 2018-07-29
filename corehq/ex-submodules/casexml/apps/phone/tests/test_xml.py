from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import os.path
from django.test import SimpleTestCase

import casexml.apps.phone.xml as xml
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex

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
        casedb_xml = xml.tostring(xml.get_casedb_element(self.case))
        self.assertXmlEqual(casedb_xml, self.get_xml('case_db_block'))
