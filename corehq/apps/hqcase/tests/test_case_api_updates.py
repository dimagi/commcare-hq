import json
from dataclasses import dataclass
from typing import Literal

from django.test import SimpleTestCase, TestCase

from ..api.updates import JsonCaseCreation
from ..views import _handle_case_update

DOMAIN = 'test-domain'


@dataclass
class FakeUser:
    user_id: str
    username: str


@dataclass
class FakeRequest:
    method: Literal['GET', 'POST', 'PUT']
    body: bytes
    META: dict[str, str]
    domain: str
    couch_user: FakeUser


class GetCaseBlockTests(SimpleTestCase):

    def setUp(self):
        self.data = {
            'case_name': 'Mark Renton',
            'case_type': 'trainspotter',
            'properties': {
                'age': '26',
            },
            'owner_id': 'abc123',
            'user_id': 'abc123',
        }

    def test_kwargs(self):
        json_case = JsonCaseCreation(self.data)
        case_block = json_case.get_caseblock(case_db=None)
        self.assertIn('<case_name>Mark Renton</case_name>', case_block)
        self.assertNotIn('<external_id', case_block)

    def test_kwargs_incl_external_id(self):
        case_data = self.data | {'external_id': 'Ewan McGregor'}
        json_case = JsonCaseCreation(case_data)
        case_block = json_case.get_caseblock(case_db=None)
        # `case_block` is something like:
        #
        #     <case case_id=""
        #           date_modified="YYYY-MM-DDTHH:MM:SS.SSSSSSZ"
        #           user_id="abc123"
        #           xmlns="http://commcarehq.org/case/transaction/v2">
        #       <create>
        #         <case_type>trainspotter</case_type>
        #         <case_name>Mark Renton</case_name>
        #         <owner_id>abc123</owner_id>
        #       </create>
        #       <update>
        #         <external_id>Ewan McGregor</external_id>
        #         <age>26</age>
        #       </update>
        #     </case>
        #
        self.assertIn('<case_type>trainspotter</case_type>', case_block)
        self.assertIn('<case_name>Mark Renton</case_name>', case_block)
        self.assertIn('<owner_id>abc123</owner_id>', case_block)
        self.assertIn('<external_id>Ewan McGregor</external_id>', case_block)
        self.assertIn('<age>26</age>', case_block)


class TestHandleCaseUpdate(TestCase):

    def test_post_empty_type(self):
        user = FakeUser(
            user_id='abc123',
            username=f'irvine@{DOMAIN}.commcarehq.org',
        )
        request = FakeRequest(
            method='POST',
            body=json.dumps({
                'case_name': 'Mark Renton',
                'case_type': '',  # Field is required, but value can be empty
                'owner_id': 'abc123'
            }).encode('utf-8'),
            META={'HTTP_USER_AGENT': __file__},
            domain=DOMAIN,
            couch_user=user,
        )
        response = _handle_case_update(request, is_creation=True)

        response_json = json.loads(response.content)
        self.assertNotIn('error', response_json)
        self.assertEqual(response_json['case']['case_name'], 'Mark Renton')
        self.assertEqual(response_json['case']['case_type'], '')
