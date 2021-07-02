import uuid
from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup

from ..api.core import serialize_case, serialize_es_case
from ..utils import submit_case_blocks


@es_test
class TestAPISerialization(TestCase):
    domain = 'test-update-cases'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.case_accessor = CaseAccessors(cls.domain)

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

        cls.parent_case = cls.case_accessor.get_case(cls.parent_case_id)
        cls.case = cls.case_accessor.get_case(case_id)
        for case in [cls.case, cls.parent_case]:
            # Patch datetimes for test consistency
            case.opened_on = datetime(2021, 2, 18, 10, 59)
            case.modified_on = datetime(2021, 2, 18, 10, 59)
            case.server_modified_on = datetime(2021, 2, 18, 10, 59)

        cls.es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)
        for case in [cls.case, cls.parent_case]:
            send_to_elasticsearch(
                'case_search',
                transform_case_for_elasticsearch(cls.case.to_json())
            )
        cls.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDownClass()

    @run_with_all_backends
    def test_serialization(self):
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

    @run_with_all_backends
    def test_es_serialization(self):
        es_case = CaseSearchES().doc_id(self.case.case_id).run().hits[0]
        self.assertEqual(serialize_case(self.case), serialize_es_case(es_case))
