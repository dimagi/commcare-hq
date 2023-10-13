from django.test import SimpleTestCase

from corehq.apps.hqcase.api.updates import JsonCaseCreation


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
