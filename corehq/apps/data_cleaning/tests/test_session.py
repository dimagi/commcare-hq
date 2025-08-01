import datetime
import uuid
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditRecord,
    BulkEditSession,
    BulkEditSessionType,
    DataType,
    FilterMatchType,
)
from corehq.apps.data_cleaning.tests.mixins import CaseDataTestMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseSearchES, group_adapter, user_adapter
from corehq.apps.es.case_search import (
    case_property_missing,
    case_search_adapter,
    exact_case_property_text_query,
)
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class BulkEditSessionTest(TestCase):
    domain_name = 'dc-session-test'
    username = 'someone@cleandata.org'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

        cls.case_type = 'child'
        cls.form_xmlns = 'http://openrosa.org/formdesigner/2423EFB5-2E8C-4B8F-9DA0-23FFFD4391AF'

    def test_has_no_active_case_session(self):
        active_session = BulkEditSession.objects.active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        assert active_session is None

    def test_has_no_active_form_session(self):
        active_session = BulkEditSession.objects.active_form_session(
            self.django_user, self.domain_name, self.form_xmlns
        )
        assert active_session is None

    def test_new_case_session(self):
        new_session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        assert new_session.session_type == BulkEditSessionType.CASE
        assert new_session.columns.count() == 6
        assert new_session.filters.count() == 0
        assert new_session.pinned_filters.count() == 2
        assert new_session.records.count() == 0
        assert new_session.changes.count() == 0

    def test_has_active_case_session(self):
        BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        active_session = BulkEditSession.objects.active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        assert active_session is not None
        assert active_session.user == self.django_user
        assert active_session.domain == self.domain_name
        assert active_session.identifier == self.case_type

    def test_has_no_active_case_session_other_type(self):
        BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        active_session = BulkEditSession.objects.active_case_session(self.django_user, self.domain_name, 'other')
        assert active_session is None

    def test_has_no_active_case_session_after_committed(self):
        case_session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        case_session.committed_on = datetime.datetime.now()
        case_session.save()
        active_session = BulkEditSession.objects.active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        assert active_session is None

    def test_has_no_active_case_session_after_completed(self):
        case_session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        case_session.committed_on = datetime.datetime.now()
        case_session.completed_on = datetime.datetime.now()
        case_session.save()
        active_session = BulkEditSession.objects.active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        assert active_session is None

    def test_restart_case_session(self):
        old_session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        old_session_id = old_session.session_id
        new_session = BulkEditSession.objects.restart_case_session(
            self.django_user,
            self.domain_name,
            self.case_type,
        )
        assert old_session_id != new_session.session_id


@es_test(requires=[case_search_adapter, user_adapter, group_adapter], setup_class=True)
class BulkEditSessionFilteredQuerysetTests(TestCase):
    domain_name = 'session-test-queryset'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain_name, get_case_blocks())

        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

        cls.case_type = 'child'

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def test_add_filters(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.0')
        filters = session.filters.all()
        for index, prop_id in enumerate(['watered_on', 'name', 'num_leaves', 'pot_type', 'height_cm']):
            assert filters[index].prop_id == prop_id
            assert filters[index].index == index

    def test_remove_filters(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.0')
        filter_to_remove = session.filters.all()[1]  # name
        assert filter_to_remove.prop_id == 'name'
        session.remove_filter(filter_to_remove.filter_id)
        filters = session.filters.all()
        assert len(filters) == 4
        for index, prop_id in enumerate(['watered_on', 'num_leaves', 'pot_type', 'height_cm']):
            assert filters[index].prop_id == prop_id
            assert filters[index].index == index

    def test_remove_column(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        column_to_remove = session.columns.all()[1]  # owner_name
        assert column_to_remove.prop_id == 'owner_name'
        session.remove_column(column_to_remove.column_id)
        columns = session.columns.all()
        assert len(columns) == 5
        for index, prop_id in enumerate(['name', 'date_opened', 'opened_by_username', 'last_modified', '@status']):
            assert columns[index].prop_id == prop_id
            assert columns[index].index == index

    def test_reorder_wrong_number_of_filter_ids_raises_error(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.0')
        filters = session.filters.all()
        # the form that uses this method will always fetch a list of strings, and the field is a UUID
        new_order = [str(filter_id) for filter_id in [filters[1].filter_id, filters[2].filter_id]]
        with pytest.raises(
            ValueError,
            match='The lengths of provided_ids and ALL existing objects do not match. '
            'Please provide a list of ALL existing object ids in the desired order.',
        ):
            session.update_filter_order(new_order)

    def test_reorder_filters(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.0')
        filters = session.filters.all()
        # the form that uses this method will always fetch a list of strings, and the field is a UUID
        new_order = [
            str(filter_id)
            for filter_id in [
                filters[1].filter_id,
                filters[0].filter_id,
                filters[2].filter_id,
                filters[4].filter_id,
                filters[3].filter_id,
            ]
        ]
        session.update_filter_order(new_order)
        reordered_prop_ids = [c.prop_id for c in session.filters.all()]
        assert reordered_prop_ids == ['name', 'watered_on', 'num_leaves', 'height_cm', 'pot_type']

    def test_reorder_wrong_number_of_column_ids_raises_error(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        columns = session.columns.all()
        # the form that uses this method will always fetch a list of strings, and the field is a UUID
        new_order = [str(col_id) for col_id in [columns[1].column_id, columns[2].column_id]]
        with pytest.raises(
            ValueError,
            match='The lengths of provided_ids and ALL existing objects do not match. '
            'Please provide a list of ALL existing object ids in the desired order.',
        ):
            session.update_column_order(new_order)

    def test_update_column_order(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        columns = session.columns.all()
        # the form that uses this method will always fetch a list of strings, and the field is a UUID
        new_order = [
            str(col_id)
            for col_id in [
                columns[1].column_id,
                columns[0].column_id,
                columns[2].column_id,
                columns[4].column_id,
                columns[5].column_id,
                columns[3].column_id,
            ]
        ]
        session.update_column_order(new_order)
        reordered_prop_ids = [c.prop_id for c in session.columns.all()]
        assert reordered_prop_ids == [
            'owner_name',
            'name',
            'date_opened',
            'last_modified',
            '@status',
            'opened_by_username',
        ]

    def test_get_queryset_multiple_filters(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_filter('pot_type', DataType.MULTIPLE_OPTION, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.1')
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .NOT(case_property_missing('watered_on'))
            .filter(exact_case_property_text_query('pot_type', ''))
            .xpath_query(
                self.domain_name, "phonetic-match(name, 'lowkey') and num_leaves > 2 and height_cm <= 11.1"
            )
        )
        assert query.es_query == expected_query.es_query

    def test_get_queryset_filters_no_xpath(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .NOT(case_property_missing('watered_on'))
        )
        assert query.es_query == expected_query.es_query

    def test_get_queryset_filters_xpath_only(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .xpath_query(self.domain_name, 'num_leaves > 2')
        )
        assert query.es_query == expected_query.es_query

    def test_has_filters_and_reset(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        assert not session.has_filters
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        assert session.has_filters
        session.reset_filters()
        assert not session.has_filters

    def test_has_pinned_values_and_reset(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        assert not session.has_pinned_values
        pinned_filter = session.pinned_filters.all()[0]
        pinned_filter.value = ['t__1']
        pinned_filter.save()
        assert session.has_pinned_values
        session.reset_pinned_filters()
        assert not session.has_pinned_values

    def test_has_any_filtering_and_reset(self):
        session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)
        assert not session.has_any_filtering
        pinned_filter = session.pinned_filters.all()[0]
        pinned_filter.value = ['t__1']
        pinned_filter.save()
        assert session.has_any_filtering
        session.reset_filtering()
        assert not session.has_any_filtering
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        assert session.has_any_filtering
        session.reset_filtering()
        assert not session.has_any_filtering


class BaseBulkEditSessionTest(TestCase):
    domain_name = None
    case_type = 'plant-friend'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(self.django_user, self.domain_name, self.case_type)


class BulkEditSessionCaseColumnTests(BaseBulkEditSessionTest):
    domain_name = 'session-test-case-columns'

    def test_add_column(self):
        assert self.session.columns.count() == 6
        new_column = self.session.add_column('num_leaves', 'Number of Leaves', DataType.INTEGER)
        assert new_column.index == 6
        assert self.session.columns.count() == 7
        assert new_column.prop_id == 'num_leaves'
        assert new_column.label == 'Number of Leaves'
        assert new_column.data_type == DataType.INTEGER
        assert not new_column.is_system

    def test_add_system_column(self):
        new_column = self.session.add_column('@owner_id', 'Owner ID', DataType.INTEGER)
        assert new_column.index == 6
        assert self.session.columns.count() == 7
        assert new_column.prop_id == '@owner_id'
        assert new_column.label == 'Owner ID'
        assert new_column.data_type == DataType.TEXT
        assert new_column.is_system


@es_test(requires=[case_search_adapter])
class BulkEditSessionSelectionCountTests(CaseDataTestMixin, BaseBulkEditSessionTest):
    domain_name = 'session-test-selection'
    case_type = 'plant'

    def test_get_num_selected_records(self):
        self.session.select_record(str(uuid.uuid4()))
        self.session.select_record(str(uuid.uuid4()))
        BulkEditRecord.objects.create(
            session=self.session,
            doc_id=str(uuid.uuid4()),
            calculated_change_id=uuid.uuid4(),
            is_selected=False,
        )
        num_selected_records = self.session.get_num_selected_records()
        assert num_selected_records == 2

    def test_get_num_selected_records_in_queryset_no_filter(self):
        case_ids = ['c1', 'c2', 'c3', 'c4', 'c5']
        cases = [{'_id': case_id, 'case_type': self.case_type} for case_id in case_ids]
        self.bootstrap_cases_in_es_for_domain(self.domain_name, cases)
        self.session.select_multiple_records(case_ids[:-1])
        num_selected = self.session.get_num_selected_records_in_queryset()
        assert num_selected == 4

    def test_get_num_selected_records_in_queryset_with_filter(self):
        self.bootstrap_cases_in_es_for_domain(
            self.domain_name, [
                {'_id': 'c1', 'case_type': self.case_type, 'soil_mix': 'chunky'},
                {'_id': 'c2', 'case_type': self.case_type, 'soil_mix': 'sandy'},
                {'_id': 'c3', 'case_type': self.case_type, 'soil_mix': 'fine'},
                {'_id': 'c4', 'case_type': self.case_type, 'soil_mix': 'chunky'},
                {'_id': 'c5', 'case_type': self.case_type, 'soil_mix': 'chunky'},
            ]
        )
        self.session.add_filter('soil_mix', DataType.TEXT, FilterMatchType.EXACT, 'chunky')
        self.session.select_multiple_records(['c1', 'c2', 'c3', 'c4'])
        num_selected = self.session.get_num_selected_records_in_queryset()
        assert num_selected == 2

    def test_get_num_unrecorded(self):
        case_ids = ['c1', 'c2', 'c3', 'c4', 'c5']
        cases = [{'_id': case_id, 'case_type': self.case_type} for case_id in case_ids]
        self.bootstrap_cases_in_es_for_domain(self.domain_name, cases)
        self.session.select_multiple_records(['c1', 'c3'])
        # simulated record with changes
        BulkEditRecord.objects.create(
            session=self.session,
            doc_id='c4',
            calculated_change_id=uuid.uuid4(),
            is_selected=False,
        )
        num_unrecorded = self.session._get_num_unrecorded()
        assert num_unrecorded == 2  # c2 and c5

    @mock.patch('corehq.apps.data_cleaning.models.session.MAX_RECORDED_LIMIT', 5)
    def test_can_select_all_is_true(self):
        case_ids = ['c1', 'c2', 'c3', 'c4', 'c5']
        cases = [{'_id': case_id, 'case_type': self.case_type} for case_id in case_ids]
        self.bootstrap_cases_in_es_for_domain(self.domain_name, cases)
        self.session.select_multiple_records(['c1', 'c3'])
        assert self.session.can_select_all()

    @mock.patch('corehq.apps.data_cleaning.models.session.MAX_RECORDED_LIMIT', 3)
    def test_can_select_all_is_false(self):
        case_ids = ['c1', 'c2', 'c3', 'c4', 'c5']
        cases = [{'_id': case_id, 'case_type': self.case_type} for case_id in case_ids]
        self.bootstrap_cases_in_es_for_domain(self.domain_name, cases)
        self.session.select_multiple_records(['c1', 'c3'])
        assert not self.session.can_select_all()

    @mock.patch('corehq.apps.data_cleaning.models.session.MAX_RECORDED_LIMIT', 3)
    def test_can_select_all_false_table_num_records(self):
        assert not self.session.can_select_all(table_num_records=4)


class BulkEditSessionChangesTests(BaseBulkEditSessionTest):
    domain_name = 'session-test-changes'

    def _get_list_of_doc_ids(self, num):
        return [str(uuid.uuid4()) for _ in range(num)]
