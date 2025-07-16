import uuid

from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditFilter,
    BulkEditSession,
    DataType,
    FilterMatchType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import (
    case_search_adapter,
)
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.util.test_utils import create_and_save_a_case


@es_test(requires=[case_search_adapter])
class BulkEditFilterValueTests(TestCase):
    domain = 'column-test-filters'
    case_type = 'plant'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

    def setUp(self):
        super().setUp()
        FormProcessorTestUtils.delete_all_cases()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            self.case_type,
        )

    def _make_case(self, domain, case_properties, index=None):
        case_properties = case_properties or {}
        case_id = case_properties.pop('_id')
        case_type = case_properties.pop('case_type', self.case_type)
        case_name = f'case-name-{uuid.uuid4().hex}'
        owner_id = case_properties.pop('owner_id', None)
        case = create_and_save_a_case(
            domain, case_id, case_name, case_properties, owner_id=owner_id, case_type=case_type, index=index
        )
        return case

    def _bootstrap_cases_in_es_for_domain(self, domain, input_cases):
        for case in input_cases:
            index = case.pop('index', None)
            self._make_case(domain, case, index=index)
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        manager.index_refresh(case_search_adapter.index_name)

    def _assert_filters_work_correctly(self, session, input_cases, expected_case_ids):
        self._bootstrap_cases_in_es_for_domain(session.domain, input_cases)
        query = session.get_queryset()
        results = query.run().hits
        actual_case_ids = [hit['_id'] for hit in results]
        assert set(actual_case_ids) == set(expected_case_ids)

    def test_is_empty_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_EMPTY,
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
            ],
            ['c2'],
        )

    def test_is_not_empty_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_NOT_EMPTY,
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
            ],
            ['c1', 'c3'],
        )

    def test_is_missing_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_MISSING,
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
            ],
            ['c1', 'c2'],
        )

    def test_is_not_missing_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_NOT_MISSING,
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
            ],
            ['c3'],
        )

    def test_exact_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='sand',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
            ],
            ['c3'],
        )

    def test_is_not_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_NOT,
            value='sand',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
            ],
            ['c1', 'c2', 'c4'],
        )

    def test_starts_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='sa',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
                {'_id': 'c5', 'case_type': self.case_type, 'soil_contents': 'sandy'},
            ],
            ['c3', 'c5'],
        )

    def test_starts_not_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS_NOT,
            value='sa',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
                {'_id': 'c5', 'case_type': self.case_type, 'soil_contents': 'sandy'},
            ],
            ['c1', 'c2', 'c4'],
        )

    def test_fuzzy_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY,
            value='sand',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
                {'_id': 'c5', 'case_type': self.case_type, 'soil_contents': 'sandy'},
            ],
            ['c3', 'c5'],
        )

    def test_fuzzy_not_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='soil_contents',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY_NOT,
            value='sand',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_contents': ''},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_contents': 'sand'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_contents': 'clay'},
                {'_id': 'c5', 'case_type': self.case_type, 'soil_contents': 'sandy'},
            ],
            ['c1', 'c2', 'c4'],
        )

    def test_phonetic_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='species',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC,
            value='birb of paradise',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'species': 'monstera'},
                {'_id': 'c2', 'case_type': self.case_type, 'species': 'bird of paradise'},
                {'_id': 'c3', 'case_type': self.case_type, 'species': 'banana'},
                {'_id': 'c4', 'case_type': self.case_type},
                {'_id': 'c5', 'case_type': self.case_type, 'species': ''},
            ],
            ['c2'],
        )

    def test_phonetic_not_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='species',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC_NOT,
            value='birb of paradise',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'species': 'monstera'},
                {'_id': 'c2', 'case_type': self.case_type, 'species': 'bird of paradise'},
                {'_id': 'c3', 'case_type': self.case_type, 'species': 'banana'},
                {'_id': 'c4', 'case_type': self.case_type},
                {'_id': 'c5', 'case_type': self.case_type, 'species': ''},
            ],
            ['c1', 'c3', 'c4', 'c5'],
        )

    def test_is_any_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='health_issues',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_ANY,
            value='yellow_leaves fungus',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'health_issues': 'yellow_leaves root_rot'},
                {'_id': 'c2', 'case_type': self.case_type, 'health_issues': 'yellow_leaves fungus'},
                {'_id': 'c3', 'case_type': self.case_type, 'health_issues': 'brown_spots root_rot'},
                {'_id': 'c4', 'case_type': self.case_type, 'health_issues': 'brown_spots'},
                {'_id': 'c5', 'case_type': self.case_type, 'health_issues': 'fungus brown_spots'},
            ],
            ['c1', 'c2', 'c5'],
        )

    def test_is_not_any_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='health_issues',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_NOT_ANY,
            value='yellow_leaves root_rot',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'health_issues': 'yellow_leaves root_rot'},
                {'_id': 'c2', 'case_type': self.case_type, 'health_issues': 'yellow_leaves fungus'},
                {'_id': 'c3', 'case_type': self.case_type, 'health_issues': 'brown_spots root_rot'},
                {'_id': 'c4', 'case_type': self.case_type, 'health_issues': 'brown_spots'},
                {'_id': 'c5', 'case_type': self.case_type, 'health_issues': 'fungus brown_spots'},
            ],
            ['c4', 'c5'],
        )

    def test_is_all_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='health_issues',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_ALL,
            value='yellow_leaves root_rot',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'health_issues': 'yellow_leaves root_rot'},
                {'_id': 'c2', 'case_type': self.case_type, 'health_issues': 'yellow_leaves fungus'},
                {'_id': 'c3', 'case_type': self.case_type, 'health_issues': 'brown_spots root_rot'},
                {'_id': 'c4', 'case_type': self.case_type, 'health_issues': 'root_rot brown_spots yellow_leaves'},
                {'_id': 'c5', 'case_type': self.case_type, 'health_issues': 'fungus brown_spots'},
            ],
            ['c1', 'c4'],
        )

    def test_is_not_all_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='health_issues',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.IS_NOT_ALL,
            value='yellow_leaves root_rot',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'health_issues': 'yellow_leaves root_rot'},
                {'_id': 'c2', 'case_type': self.case_type, 'health_issues': 'yellow_leaves fungus'},
                {'_id': 'c3', 'case_type': self.case_type, 'health_issues': 'brown_spots root_rot'},
                {'_id': 'c4', 'case_type': self.case_type, 'health_issues': 'root_rot brown_spots yellow_leaves'},
                {'_id': 'c5', 'case_type': self.case_type, 'health_issues': 'fungus brown_spots'},
            ],
            ['c2', 'c3', 'c5'],
        )

    def test_less_than_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='plant_height',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.LESS_THAN,
            value='60',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'plant_height': 30},
                {'_id': 'c2', 'case_type': self.case_type, 'plant_height': 60},
                {'_id': 'c3', 'case_type': self.case_type, 'plant_height': 40},
                {'_id': 'c4', 'case_type': self.case_type, 'plant_height': 70},
            ],
            ['c1', 'c3'],
        )

    def test_greater_than_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='plant_height',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN,
            value='40',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'plant_height': 30},
                {'_id': 'c2', 'case_type': self.case_type, 'plant_height': 60},
                {'_id': 'c3', 'case_type': self.case_type, 'plant_height': 40},
                {'_id': 'c4', 'case_type': self.case_type, 'plant_height': 70},
            ],
            ['c2', 'c4'],
        )

    def test_less_than_equal_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='plant_height',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.LESS_THAN_EQUAL,
            value='60',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'plant_height': 30},
                {'_id': 'c2', 'case_type': self.case_type, 'plant_height': 60},
                {'_id': 'c3', 'case_type': self.case_type, 'plant_height': 40},
                {'_id': 'c4', 'case_type': self.case_type, 'plant_height': 70},
            ],
            ['c1', 'c2', 'c3'],
        )

    def test_greater_than_equal_filter(self):
        BulkEditFilter.objects.create(
            session=self.session,
            prop_id='plant_height',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN_EQUAL,
            value='40',
        )
        self._assert_filters_work_correctly(
            self.session,
            [
                {'_id': 'c1', 'case_type': self.case_type, 'plant_height': 30},
                {'_id': 'c2', 'case_type': self.case_type, 'plant_height': 60},
                {'_id': 'c3', 'case_type': self.case_type, 'plant_height': 40},
                {'_id': 'c4', 'case_type': self.case_type, 'plant_height': 70},
            ],
            ['c2', 'c3', 'c4'],
        )
