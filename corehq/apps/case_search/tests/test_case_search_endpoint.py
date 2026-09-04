import datetime
import uuid
from unittest import mock

from django.test import TestCase

import pytest
from lxml import etree
from unmagic import fixture, use

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
    CaseSearchEndpointVersion,
    CaseSearchRequestConfig,
    SearchCriteria,
)
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.apps.project_db.populate import populate_case_type
from corehq.apps.project_db.tests.util import project_db_table
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.tests.util.xml import assert_xml_equal
from corehq.util.test_utils import flag_enabled

from ..utils import get_case_search_results, get_project_db_fixture


@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseSearchEndpoint(TestCase):
    domain = "TestCaseSearchEndpoint"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_user("admin", "123")
        CaseSearchConfig.objects.create(domain=cls.domain, enabled=True)
        cls.person_case_type = CaseType.objects.create(domain=cls.domain, name='person')
        cls.addClassCleanup(cls.person_case_type.delete)
        # the endpoint query builder validates fields against the data dictionary
        CaseProperty.objects.create(
            case_type=cls.person_case_type,
            name='family',
            data_type=CaseProperty.DataType.PLAIN,
        )
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

    def _make_es_endpoint(self, query, parameters=None):
        endpoint = CaseSearchEndpoint.objects.create(
            domain=self.domain,
            name='people',
            target_type=CaseSearchEndpoint.TargetType.ELASTICSEARCH,
        )
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=endpoint,
            version_number=1,
            case_type='person',
            query=query,
            parameters=parameters or [],
            action=CaseSearchEndpointVersion.Action.CREATE,
        )
        endpoint.current_version = version
        endpoint.save(update_fields=['current_version'])
        return endpoint

    @flag_enabled('CASE_SEARCH_ENDPOINTS')
    def test_endpoint_id_runs_query(self):
        endpoint = self._make_es_endpoint({'type': 'all', 'children': []})
        res = self._run_query(['person'], [], endpoint_id=endpoint.id)
        self.assertItemsEqual(["Jane", "Xiomara", "Alba", "Rogelio", "Jane"], [
            case.name for case in res
        ])

    @flag_enabled('CASE_SEARCH_ENDPOINTS')
    def test_endpoint_text_parameter(self):
        endpoint = self._make_es_endpoint(
            query={
                'type': 'all',
                'children': [{
                    'type': 'component',
                    'field': 'family',
                    'operator': 'equals',
                    'inputs': {'value': {'type': 'parameter', 'value': 'family'}},
                }],
            },
            parameters=[{'name': 'family', 'type': 'text'}],
        )
        res = self._run_query(
            ['person'], [SearchCriteria('family', 'Ramos')], endpoint_id=endpoint.id)
        self.assertItemsEqual(["Jane"], [case.name for case in res])

    @flag_enabled('CASE_SEARCH_ENDPOINTS')
    def test_endpoint_text_parameter_not_supplied(self):
        # an unsupplied parameter drops its condition rather than filtering on ''
        endpoint = self._make_es_endpoint(
            query={
                'type': 'all',
                'children': [{
                    'type': 'component',
                    'field': 'family',
                    'operator': 'equals',
                    'inputs': {'value': {'type': 'parameter', 'value': 'family'}},
                }],
            },
            parameters=[{'name': 'family', 'type': 'text'}],
        )
        res = self._run_query(['person'], [], endpoint_id=endpoint.id)
        self.assertItemsEqual(["Jane", "Xiomara", "Alba", "Rogelio", "Jane"], [
            case.name for case in res
        ])

    @flag_enabled('CASE_SEARCH_ENDPOINTS')
    def test_unknown_endpoint_id_raises(self):
        with self.assertRaises(CaseSearchUserError):
            self._run_query(['person'], [], endpoint_id=404)


SQL_DOMAIN = 'test-endpoint-sql'
PETS = [
    ('p1', 'Fido', 'brown', '20'),
    ('p2', 'Rex', 'black', '5'),
]


@fixture(scope="module")
def pet_table():
    # The pets are read but never written, so the table is built once for
    # every test in the module rather than per test.
    with project_db_table(SQL_DOMAIN, 'pet', {'color': 'plain', 'weight': 'number'}):
        _populate_pets()
        yield


def _make_sql_endpoint(sql):
    endpoint = CaseSearchEndpoint.objects.create(
        domain=SQL_DOMAIN,
        name='pets',
        target_type=CaseSearchEndpoint.TargetType.PROJECT_DB,
    )
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=1,
        case_type='pet',
        dangerous_sql=sql,
        action=CaseSearchEndpointVersion.Action.CREATE,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return endpoint


def _populate_pets():
    populate_case_type(SQL_DOMAIN, 'pet', [
        CommCareCase(
            case_id=case_id,
            domain=SQL_DOMAIN,
            type='pet',
            name=name,
            owner_id='owner1',
            opened_on=datetime.datetime(2025, 1, 1),
            modified_on=datetime.datetime(2025, 6, 1),
            server_modified_on=datetime.datetime(2025, 6, 1),
            closed=False,
            external_id='',
            case_json={'color': color, 'weight': weight},
            indices=[],
        ) for case_id, name, color, weight in PETS
    ])


def _run_sql_query(endpoint, criteria):
    config = CaseSearchRequestConfig(
        criteria=[SearchCriteria(key, value) for key, value in criteria.items()],
        case_types=['pet'],
        endpoint_id=endpoint.id,
    )
    return get_project_db_fixture(SQL_DOMAIN, endpoint, config)


@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_returns_selected_columns():
    _populate_pets()
    endpoint = _make_sql_endpoint(
        'SELECT case_id, case_name, prop__color AS color FROM pet ORDER BY case_id')
    fixture = _run_sql_query(endpoint, {})
    assert_xml_equal("""
    <results id="case">
        <case case_id="p1">
            <case_id>p1</case_id>
            <case_name>Fido</case_name>
            <color>brown</color>
        </case>
        <case case_id="p2">
            <case_id>p2</case_id>
            <case_name>Rex</case_name>
            <color>black</color>
        </case>
    </results>""", fixture)


COLOR_SQL = "SELECT * FROM pet WHERE (:color IS NULL OR prop__color = :color)"
WEIGHT_SQL = "SELECT * FROM pet WHERE (:weight IS NULL OR number_prop__weight > :weight)"


@pytest.mark.parametrize('sql, criteria, expected', [
    (COLOR_SQL, {'color': 'brown'}, ['Fido']),
    (COLOR_SQL, {'color': 'black'}, ['Rex']),
    (COLOR_SQL, {'color': 'chartreuse'}, []),
    (COLOR_SQL, {}, ['Fido', 'Rex']),
    (COLOR_SQL, {'color': ''}, ['Fido', 'Rex']),
    (WEIGHT_SQL, {'weight': '12'}, ['Fido']),
    (WEIGHT_SQL, {'weight': '1'}, ['Fido', 'Rex']),
    (WEIGHT_SQL, {'weight': '100'}, []),
    (WEIGHT_SQL, {}, ['Fido', 'Rex']),
    (WEIGHT_SQL, {'weight': ''}, ['Fido', 'Rex']),
])
@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_with_text_parameter(sql, criteria, expected):
    _populate_pets()
    endpoint = _make_sql_endpoint(sql)
    fixture = _run_sql_query(endpoint, criteria)
    names = sorted(case.findtext('case_name') for case in etree.fromstring(fixture))
    assert names == expected
