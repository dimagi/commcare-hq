import datetime
import uuid
from unittest import mock

from django.test import TestCase

import pytest
from unmagic import fixture, use

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.case_search.const import IS_RELATED_CASE
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
    CaseSearchRequestConfig,
    SearchCriteria,
)
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.project_db.populate import send_to_project_db
from corehq.apps.project_db.tests.util import project_db_table
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import flag_enabled

from ..utils import get_case_search_results


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
PET_PROPERTIES = {
    'color': 'plain',
    'weight': 'number',
    'species': 'select',
    'shot_due': 'date',
}
PETS = [
    ('p1', 'Fido', {'color': 'brown', 'weight': '20',
                    'species': 'dog', 'shot_due': '2026-08-18'}),
    ('p2', 'Rex', {'color': 'black', 'weight': '5',
                   'species': 'cat lion', 'shot_due': '2026-01-05'}),
]


@fixture
def pet_table():
    with project_db_table(SQL_DOMAIN, 'pet', PET_PROPERTIES):
        yield


def _make_sql_endpoint(sql, parameters=None):
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
        parameters=parameters or [],
        action=CaseSearchEndpointVersion.Action.CREATE,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return endpoint


def _populate_pets():
    send_to_project_db(SQL_DOMAIN, 'pet', [
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
            case_json=properties,
            indices=[],
        ) for case_id, name, properties in PETS
    ])


def _run_sql_query(endpoint, criteria):
    config = CaseSearchRequestConfig(
        criteria=criteria, case_types=['pet'], endpoint_id=endpoint.id)
    return get_case_search_results(SQL_DOMAIN, config)


@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_without_parameters():
    _populate_pets()
    endpoint = _make_sql_endpoint('SELECT * FROM pet')

    cases = sorted(_run_sql_query(endpoint, []), key=lambda case: case.name)

    assert [case.name for case in cases] == ['Fido', 'Rex']
    assert [case.case_id for case in cases] == ['p1', 'p2']
    assert [case.case_json for case in cases] == [props for _, _, props in PETS]
    assert all(case.domain == SQL_DOMAIN and case.type == 'pet' for case in cases)


COLOR_SQL = (
    "SELECT * FROM pet "
    "WHERE (:color IS NULL OR prop__color = :color)"
)


@pytest.mark.parametrize('criteria, expected', [
    ([SearchCriteria('color', 'brown')], ['Fido']),
    ([SearchCriteria('color', 'black')], ['Rex']),
    ([SearchCriteria('color', 'chartreuse')], []),
    # an unsupplied or blank parameter is passed as NULL, which the guard
    # treats as "any"
    ([], ['Fido', 'Rex']),
    ([SearchCriteria('color', '')], ['Fido', 'Rex']),
])
@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_with_text_parameter(criteria, expected):
    _populate_pets()
    endpoint = _make_sql_endpoint(COLOR_SQL, [{'name': 'color', 'type': 'text'}])

    cases = _run_sql_query(endpoint, criteria)

    assert sorted(case.name for case in cases) == expected


WEIGHT_SQL = (
    "SELECT * FROM pet "
    "WHERE (:weight IS NULL OR number_prop__weight > :weight)"
)


@pytest.mark.parametrize('criteria, expected', [
    ([SearchCriteria('weight', '12')], ['Fido']),
    ([SearchCriteria('weight', '1')], ['Fido', 'Rex']),
    ([SearchCriteria('weight', '100')], []),
    # NULL is the only sentinel that coerces to a numeric column; an empty
    # string would fail with "invalid input syntax for type numeric"
    ([], ['Fido', 'Rex']),
    ([SearchCriteria('weight', '')], ['Fido', 'Rex']),
])
@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_with_number_parameter(criteria, expected):
    _populate_pets()
    endpoint = _make_sql_endpoint(WEIGHT_SQL, [{'name': 'weight', 'type': 'number'}])

    cases = _run_sql_query(endpoint, criteria)

    assert sorted(case.name for case in cases) == expected


SPECIES_SQL = (
    "SELECT * FROM pet "
    "WHERE (:species IS NULL OR select_prop__species && :species)"
)


@pytest.mark.parametrize('criteria, expected', [
    # A select parameter is bound as a list however many values were searched
    ([SearchCriteria('species', 'dog')], ['Fido']),
    ([SearchCriteria('species', ['dog', 'lion'])], ['Fido', 'Rex']),
    ([SearchCriteria('species', 'fish')], []),
    ([], ['Fido', 'Rex']),
    ([SearchCriteria('species', '')], ['Fido', 'Rex']),
])
@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_with_select_parameter(criteria, expected):
    _populate_pets()
    endpoint = _make_sql_endpoint(
        SPECIES_SQL, [{'name': 'species', 'type': 'select'}])

    cases = _run_sql_query(endpoint, criteria)

    assert sorted(case.name for case in cases) == expected


DUE_SQL = (
    "SELECT * FROM pet "
    "WHERE (:due_from IS NULL OR date_prop__shot_due >= :due_from) "
    "AND (:due_to IS NULL OR date_prop__shot_due <= :due_to)"
)


@pytest.mark.parametrize('criteria, expected', [
    # One criterion named for the parameter fills both of its placeholders
    ([SearchCriteria('due', '__range__2026-08-03__2026-08-20')], ['Fido']),
    ([SearchCriteria('due', '__range__2026-01-01__2026-12-31')], ['Fido', 'Rex']),
    ([SearchCriteria('due', '__range__2020-01-01__2020-12-31')], []),
    ([], ['Fido', 'Rex']),
])
@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_with_daterange_parameter(criteria, expected):
    _populate_pets()
    endpoint = _make_sql_endpoint(
        DUE_SQL, [{'name': 'due', 'type': 'daterange'}])

    cases = _run_sql_query(endpoint, criteria)

    assert sorted(case.name for case in cases) == expected


@use('db', pet_table)
@flag_enabled('CASE_SEARCH_ENDPOINTS')
def test_sql_endpoint_rejects_multiple_values_for_a_text_parameter():
    _populate_pets()
    endpoint = _make_sql_endpoint(COLOR_SQL, [{'name': 'color', 'type': 'text'}])

    with pytest.raises(CaseSearchUserError, match="Only one value may be given"):
        _run_sql_query(endpoint, [SearchCriteria('color', ['brown', 'black'])])
