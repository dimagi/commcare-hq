import uuid
from unittest import mock

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.case_search.const import IS_RELATED_CASE
from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchEndpoint,
    CaseSearchRequestConfig,
    SearchCriteria,
)
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils

from ..utils import get_case_search_results


@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseSearchEndpoint(TestCase):
    domain = "TestCaseSearchEndpoint"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_user("admin", "123")
        CaseSearchConfig.objects.create(domain=cls.domain, enabled=True)
        cls.household_1 = str(uuid.uuid4())
        case_blocks = [CaseBlock(
            case_id=cls.household_1,
            case_type='household',
            case_name="Villanueva",
            create=True,
        )]
        case_blocks.extend([CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='person',
            case_name=name,
            create=True,
            update=properties,
            index={'parent': IndexAttrs('household', household_id, 'child')} if household_id else None,
        ) for name, properties, household_id in [
            ("Jane", {"family": "Villanueva"}, cls.household_1),
            ("Xiomara", {"family": "Villanueva"}, cls.household_1),
            ("Alba", {"family": "Villanueva"}, cls.household_1),
            ("Rogelio", {"family": "de la Vega"}, cls.household_1),
            ("Jane", {"family": "Ramos"}, None),
        ]])
        case_search_es_setup(cls.domain, case_blocks)

        cls.factory = AppFactory(domain=cls.domain)
        module, form = cls.factory.new_basic_module('person', 'person')
        module.search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name')]
        )
        module.case_details.short.columns = [
            DetailColumn(format='plain', field=field, header={'en': field}, model='person')
            for field in ['name', 'parent/name']
        ]

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def _run_query(self, case_types, criteria, app_id=None, endpoint_id=None):
        config = CaseSearchRequestConfig(
            criteria=criteria, case_types=case_types, endpoint_id=endpoint_id)
        return get_case_search_results(self.domain, config, app_id=app_id)

    def test_basic(self):
        res = self._run_query(['person'], [])
        self.assertItemsEqual(["Jane", "Xiomara", "Alba", "Rogelio", "Jane"], [
            case.name for case in res
        ])

    def test_case_id_criteia(self):
        res = self._run_query(['household'], [SearchCriteria('case_id', self.household_1)])
        self.assertItemsEqual(["Villanueva"], [case.name for case in res])

    def test_dynamic_property(self):
        res = self._run_query(['person'], [SearchCriteria('family', 'Ramos')])
        self.assertItemsEqual(["Jane"], [case.name for case in res])

    def test_app_aware_related_cases(self):
        with mock.patch('corehq.apps.case_search.utils.get_app_cached', new=lambda _, __: self.factory.app):
            res = self._run_query(['person'], [], app_id='fake_app_id')
        self.assertItemsEqual([
            (case.name, case.get_case_property(IS_RELATED_CASE)) for case in res
        ], [
            ("Jane", None),
            ("Xiomara", None),
            ("Alba", None),
            ("Rogelio", None),
            ("Jane", None),
            ("Villanueva", "true"),
        ])

    def test_endpoint_id_runs_query(self):
        endpoint = CaseSearchEndpoint.objects.create(
            domain=self.domain, name='people', target_name='elasticsearch')
        res = self._run_query(['person'], [SearchCriteria('family', 'Ramos')], endpoint_id=endpoint.id)
        self.assertItemsEqual(["Jane"], [case.name for case in res])

    def test_unknown_endpoint_id_raises(self):
        with self.assertRaises(CaseSearchUserError):
            self._run_query(['person'], [], endpoint_id=404)
