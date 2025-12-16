from unittest.mock import Mock

from django.test import SimpleTestCase

from corehq.apps.hqcase.api.updates import JsonCaseCreation, JsonCaseUpsert


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


class JsonCaseUpsertTests(SimpleTestCase):

    def setUp(self):
        self.data = {
            'case_name': 'John Doe',
            'case_type': 'patient',
            'external_id': 'ext-123',
            'owner_id': 'owner-abc',
            'user_id': 'user-xyz',
            'properties': {'status': 'active'},
        }

    def test_get_case_id_when_case_exists(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = 'existing-case-id'

        case_id = upsert.get_case_id(case_db)

        self.assertEqual(case_id, 'existing-case-id')
        self.assertFalse(upsert._is_case_creation)
        case_db.get_upsert_case_id.assert_called_once_with('ext-123')

    def test_get_case_id_when_case_does_not_exist(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_id = upsert.get_case_id(case_db)

        self.assertIsNotNone(case_id)
        self.assertEqual(len(case_id), 36)  # UUID format
        self.assertTrue(upsert._is_case_creation)

    def test_get_case_id_is_idempotent(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_id_1 = upsert.get_case_id(case_db)
        case_id_2 = upsert.get_case_id(case_db)

        self.assertEqual(case_id_1, case_id_2)
        # Should only call case_db once due to caching
        case_db.get_upsert_case_id.assert_called_once()

    def test_get_caseblock_for_creation(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_block = upsert.get_caseblock(case_db)

        self.assertIn('<create>', case_block)
        self.assertIn('<case_type>patient</case_type>', case_block)
        self.assertIn('<case_name>John Doe</case_name>', case_block)
        self.assertIn('<owner_id>owner-abc</owner_id>', case_block)

    def test_get_caseblock_for_update(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = 'existing-case-id'

        case_block = upsert.get_caseblock(case_db)

        self.assertNotIn('<create>', case_block)
        self.assertIn('<update>', case_block)
        self.assertIn('<status>active</status>', case_block)

    def test_is_new_case_initially_none(self):
        upsert = JsonCaseUpsert(self.data)
        self.assertIsNone(upsert.is_new_case)
