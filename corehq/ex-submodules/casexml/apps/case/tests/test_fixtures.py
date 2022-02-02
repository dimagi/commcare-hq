import datetime
import os.path

from django.test import SimpleTestCase

from casexml.apps.case.fixtures import CaseDBFixture
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.form_processor.models import CommCareCase


class TestFixtures(TestXmlMixin, SimpleTestCase):
    root = os.path.dirname(__file__)
    file_path = ['data']

    domain = 'winterfell'

    def create_case(self):
        return CommCareCase(
            case_id='redwoman',
            domain=self.domain,
            opened_on=datetime.datetime(2016, 5, 31),
            modified_on=datetime.datetime(2016, 5, 31),
            type='priestess',
            closed=False,
            name='melisandre',
            owner_id='lordoflight',
            indices=[{
                'identifier': 'advisor',
                'referenced_type': 'human',
                'referenced_id': 'stannis',
                'relationship': 'extension',
            }],
            case_json={'power': 'prophecy', 'hometown': 'asshai'},
        )

    def test_fixture(self):
        case = self.create_case()
        fixture = CaseDBFixture([case, case]).fixture
        self.assertXmlEqual(self.get_xml('case_fixture'), fixture)
