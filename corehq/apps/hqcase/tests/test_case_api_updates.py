from unittest.mock import Mock

from django.test import SimpleTestCase

import pytest

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
        assert '<case_name>Mark Renton</case_name>' in case_block
        assert '<external_id' not in case_block

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
        assert '<case_type>trainspotter</case_type>' in case_block
        assert '<case_name>Mark Renton</case_name>' in case_block
        assert '<owner_id>abc123</owner_id>' in case_block
        assert '<external_id>Ewan McGregor</external_id>' in case_block
        assert '<age>26</age>' in case_block


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

        assert case_id == 'existing-case-id'
        assert not upsert._is_case_creation
        case_db.get_upsert_case_id.assert_called_once_with('ext-123')

    def test_get_case_id_when_case_does_not_exist(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_id = upsert.get_case_id(case_db)

        assert case_id is not None
        assert len(case_id) == 36  # UUID format
        assert upsert._is_case_creation

    def test_get_case_id_is_idempotent(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_id_1 = upsert.get_case_id(case_db)
        case_id_2 = upsert.get_case_id(case_db)

        assert case_id_1 == case_id_2
        # Should only call case_db once due to caching
        case_db.get_upsert_case_id.assert_called_once()

    def test_get_caseblock_for_creation(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = None

        case_block = upsert.get_caseblock(case_db)

        assert '<create>' in case_block
        assert '<case_type>patient</case_type>' in case_block
        assert '<case_name>John Doe</case_name>' in case_block
        assert '<owner_id>owner-abc</owner_id>' in case_block

    def test_get_caseblock_for_update(self):
        upsert = JsonCaseUpsert(self.data)
        case_db = Mock()
        case_db.get_upsert_case_id.return_value = 'existing-case-id'

        case_block = upsert.get_caseblock(case_db)

        assert '<create>' not in case_block
        assert '<update>' in case_block
        assert '<status>active</status>' in case_block

    def test_is_new_case_not_initialized(self):
        upsert = JsonCaseUpsert(self.data)
        with pytest.raises(
            ValueError,
            match='is_new_case has not yet been initialized',
        ):
            upsert.is_new_case
