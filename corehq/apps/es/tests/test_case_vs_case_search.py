import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseES, CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted


class TestCaseSearchESvCaseES(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'case_v_case_search'
        cls.domain_obj = create_domain(cls.domain)
        cls.case_type = 'person'
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)

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

        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, CASE_INDEX_INFO)
        initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)
        for case in [cls.case, cls.parent_case]:
            send_to_elasticsearch('cases', case.to_json())
            send_to_elasticsearch(
                'case_search',
                transform_case_for_elasticsearch(cls.case.to_json())
            )
        cls.es.indices.refresh(CASE_INDEX_INFO.index)
        cls.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDownClass()

    def test(self):
        case_doc = CaseES().doc_id(self.case.case_id).run().hits[0]
        case_search_doc = CaseSearchES().doc_id(self.case.case_id).run().hits[0]
        self.assertItemsEqual(list(case_doc.keys()), list(case_search_doc.keys()))
        self.assertEqual(case_doc, case_search_doc)
