from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

import os.path
from casexml.apps.case.fixtures import CaseDBFixture
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.app_manager.tests.util import TestXmlMixin
from django.test import SimpleTestCase


class TestFixtures(TestXmlMixin, SimpleTestCase):
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

    def test_fixture(self):
        fixture = CaseDBFixture([self.case, self.case]).fixture
        self.assertXmlEqual(fixture, self.get_xml('case_fixture'))
