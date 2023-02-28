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
from corehq.apps.case_search.models import CaseSearchConfig, SearchCriteria
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
        household_1 = str(uuid.uuid4())
        case_blocks = [CaseBlock(
            case_id=household_1,
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
            ("Jane", {"family": "Villanueva"}, household_1),
            ("Xiomara", {"family": "Villanueva"}, household_1),
            ("Alba", {"family": "Villanueva"}, household_1),
            ("Rogelio", {"family": "de la Vega"}, household_1),
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

    def test_basic(self):
        res = get_case_search_results(self.domain, ['person'], [])
        self.assertItemsEqual(["Jane", "Xiomara", "Alba", "Rogelio", "Jane"], [
            case.name for case in res
        ])

    def test_dynamic_property(self):
        res = get_case_search_results(self.domain, ['person'], [SearchCriteria('family', 'Ramos')])
        self.assertItemsEqual(["Jane"], [case.name for case in res])

    def test_app_aware_related_cases(self):
        with mock.patch('corehq.apps.case_search.utils.get_app_cached', new=lambda _, __: self.factory.app):
            res = get_case_search_results(self.domain, ['person'], [], app_id='fake_app_id')
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
