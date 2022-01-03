from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import get_case_history
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.pillows.mappings import CASE_INDEX_INFO, XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted


@es_test
class TestCaseHistory(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCaseHistory, cls).setUpClass()
        cls.es = [{
            'info': index_info,
            'instance': get_es_new(),
        } for index_info in [CASE_INDEX_INFO, XFORM_INDEX_INFO]]

    @classmethod
    def tearDownClass(cls):
        for es in cls.es:
            ensure_index_deleted(es['info'].index)
        super(TestCaseHistory, cls).tearDownClass()

    def setUp(self):
        for es in self.es:
            ensure_index_deleted(es['info'].index)
            initialize_index_and_mapping(es['instance'], es['info'])
        self.domain = "isildur"
        self.factory = CaseFactory(self.domain)
        self.case = self.factory.create_case(owner_id='owner', case_name="Aragorn", update={"prop_1": "val1"})
        self.other_case = self.factory.create_case()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()

    def test_case_history(self):
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'prop_1': "val1",
                        'prop_2': "val1",
                        'prop_3': "val1",
                    },
                }),
        )
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'prop_1': "val2",
                        'prop_2': "val2",
                        'prop_4': "val",
                    },
                }),
        )
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        history = get_case_history(case)
        self.assertEqual(history[0]['prop_1'], "val1")
        self.assertEqual(history[1]['prop_2'], "val1")
        self.assertEqual(history[2]['prop_2'], "val2")
