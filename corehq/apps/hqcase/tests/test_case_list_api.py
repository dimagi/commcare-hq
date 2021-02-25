import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from pillowtop.es_utils import initialize_index_and_mapping

from corehq import privileges
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import (
    generate_cases,
    privilege_enabled,
    trap_extra_setup,
)

from ..api.core import UserError
from ..api.get_list import get_list
from ..utils import submit_case_blocks


@es_test
@privilege_enabled(privileges.API_ACCESS)
class TestCaseListAPI(TestCase):
    domain = 'testcaselistapi'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = cls._mk_cases([
            ('mattie', "Mattie Ross", {}),
            ('rooster', "Reuben Cogburn", {"alias": "Rooster"}),
            ('laboeuf', "LaBoeuf", {}),
            ('chaney', "Tom Chaney", {"alias": "The Coward"}),
            ('ned', "Ned Pepper", {"alias": "Lucky Ned"}),
        ])

        cls.es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)
        for case in cls.cases:
            send_to_elasticsearch(
                'case_search',
                transform_case_for_elasticsearch(case.to_json())
            )
        cls.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    @classmethod
    def _mk_cases(cls, case_specs):
        _, cases = submit_case_blocks([
            CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type='person',
                case_name=name,
                external_id=external_id,
                owner_id='owner',
                create=True,
                update=properties,
            ).as_text()
            for external_id, name, properties in case_specs
        ], domain=cls.domain)

        # preserve ordering
        order = {external_id: index for index, (external_id, _, __) in enumerate(case_specs)}
        return sorted(cases, key=lambda case: order[case.external_id])

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDownClass()


@generate_cases([
    ({}, ['mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
    ({'limit': 2}, ['mattie', 'rooster']),
], TestCaseListAPI)
def test_case_list_queries(self, params, expected):
    actual = [c['external_id'] for c in get_list(self.domain, params)]
    # order matters, so this doesn't use assertItemsEqual
    self.assertEqual(actual, expected)


@generate_cases([
    ({'limit': 10000}, "You cannot request more than 5000 cases per request."),
], TestCaseListAPI)
def test_bad_requests(self, params, error_msg):
    with self.assertRaises(UserError) as e:
        get_list(self.domain, params)
    self.assertEqual(str(e.exception), error_msg)
