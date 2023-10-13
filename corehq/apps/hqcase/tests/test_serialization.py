import uuid
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import CaseSearchES, case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.models import CommCareCase

from ..api.core import serialize_case, serialize_es_case
from ..utils import submit_case_blocks


@es_test(requires=[case_search_adapter], setup_class=True)
class TestAPISerialization(TestCase):
    domain = 'test-update-cases'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        cls.parent_case_id = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        xform, cases = submit_case_blocks([
            CaseBlock(
                case_id=cls.parent_case_id,
                case_type='player',
                case_name='Elizabeth Harmon',
                external_id='1',
                owner_id='methuen_home',
                create=True,
                update={
                    'sport': 'chess',
                    'rank': '1600',
                    'dob': '1948-11-02',
                }
            ).as_text(),
            CaseBlock(
                case_id=case_id,
                case_type='match',
                case_name='Harmon/Luchenko',
                owner_id='harmon',
                external_id='14',
                create=True,
                update={
                    'winner': 'Harmon',
                    'accuracy': '84.3',
                },
                index={
                    'parent': IndexAttrs(case_type='player', case_id=cls.parent_case_id, relationship='child')
                },
            ).as_text()
        ], domain=cls.domain)

        cls.parent_case = CommCareCase.objects.get_case(cls.parent_case_id, cls.domain)
        cls.case = CommCareCase.objects.get_case(case_id, cls.domain)
        for case in [cls.case, cls.parent_case]:
            # Patch datetimes for test consistency
            case.opened_on = datetime(2021, 2, 18, 10, 59)
            case.modified_on = datetime(2021, 2, 18, 10, 59)
            case.server_modified_on = datetime(2021, 2, 18, 10, 59)

        for case in [cls.case, cls.parent_case]:
            case_search_adapter.index(
                cls.case,
                refresh=True
            )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    @patch('corehq.apps.hqcase.api.core.datetime')
    def test_serialization(self, datetime_mock):
        datetime_mock.utcnow.return_value = datetime(2021, 2, 18, 11, 2)
        self.assertEqual(
            serialize_case(self.case),
            {
                "domain": self.domain,
                "case_id": self.case.case_id,
                "case_type": "match",
                "case_name": "Harmon/Luchenko",
                "external_id": "14",
                "owner_id": "harmon",
                "date_opened": "2021-02-18T10:59:00.000000Z",
                "last_modified": "2021-02-18T10:59:00.000000Z",
                "server_last_modified": "2021-02-18T10:59:00.000000Z",
                "indexed_on": "2021-02-18T11:02:00.000000Z",
                "closed": False,
                "date_closed": None,
                "properties": {
                    "winner": "Harmon",
                    'accuracy': '84.3',
                },
                "indices": {
                    "parent": {
                        "case_id": self.parent_case_id,
                        "case_type": "player",
                        "relationship": "child",
                    }
                }
            }
        )

    def test_es_serialization(self):
        es_case = CaseSearchES().doc_id(self.case.case_id).run().hits[0]
        sql_res = serialize_case(self.case)
        es_res = serialize_es_case(es_case)

        # Remove indexed on, as this will vary slightly, which is expected
        sql_res.pop('indexed_on')
        es_res.pop('indexed_on')

        self.assertEqual(sql_res, es_res)
