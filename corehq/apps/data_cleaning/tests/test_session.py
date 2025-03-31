import datetime

from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditSession,
    BulkEditSessionType,
    DataType,
    FilterMatchType,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseSearchES, user_adapter, group_adapter
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.apps.reports.standard.cases.utils import all_project_data_filter
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

        cls.web_user = WebUser.create(
            cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None
        )
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

        cls.case_type = 'child'
        cls.form_xmlns = 'http://openrosa.org/formdesigner/2423EFB5-2E8C-4B8F-9DA0-23FFFD4391AF'

    def test_has_no_active_case_session(self):
        active_session = BulkEditSession.get_active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        self.assertIsNone(active_session)

    def test_has_no_active_form_session(self):
        active_session = BulkEditSession.get_active_form_session(
            self.django_user, self.domain_name, self.form_xmlns
        )
        self.assertIsNone(active_session)

    def test_new_case_session(self):
        new_session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        self.assertEqual(new_session.session_type, BulkEditSessionType.CASE)
        self.assertEqual(new_session.columns.count(), 6)
        self.assertEqual(new_session.filters.count(), 0)
        self.assertEqual(new_session.pinned_filters.count(), 2)
        self.assertEqual(new_session.records.count(), 0)
        self.assertEqual(new_session.changes.count(), 0)

    def test_has_active_case_session(self):
        BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        active_session = BulkEditSession.get_active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        self.assertIsNotNone(active_session)
        self.assertEqual(active_session.user, self.django_user)
        self.assertEqual(active_session.domain, self.domain_name)
        self.assertEqual(active_session.identifier, self.case_type)

    def test_has_no_active_case_session_other_type(self):
        BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        active_session = BulkEditSession.get_active_case_session(
            self.django_user, self.domain_name, 'other'
        )
        self.assertIsNone(active_session)

    def test_has_no_active_case_session_after_committed(self):
        case_session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        case_session.committed_on = datetime.datetime.now()
        case_session.save()
        active_session = BulkEditSession.get_active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        self.assertIsNone(active_session)

    def test_has_no_active_case_session_after_completed(self):
        case_session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        case_session.committed_on = datetime.datetime.now()
        case_session.completed_on = datetime.datetime.now()
        case_session.save()
        active_session = BulkEditSession.get_active_case_session(
            self.django_user, self.domain_name, self.case_type
        )
        self.assertIsNone(active_session)

    def test_restart_case_session(self):
        old_session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        old_session_id = old_session.session_id
        new_session = BulkEditSession.restart_case_session(self.django_user, self.domain_name, self.case_type)
        self.assertNotEqual(old_session_id, new_session.session_id)


@es_test(requires=[case_search_adapter, user_adapter, group_adapter], setup_class=True)
class BulkEditSessionFilteredQuerysetTests(TestCase):
    domain_name = 'session-test-queryset'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain_name, get_case_blocks())

        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(
            cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None
        )
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

        cls.case_type = 'child'

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def test_add_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        filters = session.filters.all()
        for index, prop_id in enumerate(['watered_on', 'name', 'num_leaves', 'pot_type', 'height_cm']):
            self.assertEqual(filters[index].prop_id, prop_id)
            self.assertEqual(filters[index].index, index)

    def test_remove_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        filter_to_remove = session.filters.all()[1]  # name
        self.assertEqual(filter_to_remove.prop_id, 'name')
        session.remove_filter(filter_to_remove.filter_id)
        filters = session.filters.all()
        self.assertEqual(len(filters), 4)
        for index, prop_id in enumerate(['watered_on', 'num_leaves', 'pot_type', 'height_cm']):
            self.assertEqual(filters[index].prop_id, prop_id)
            self.assertEqual(filters[index].index, index)

    def test_remove_column(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        column_to_remove = session.columns.all()[1]  # owner_name
        self.assertEqual(column_to_remove.prop_id, 'owner_name')
        session.remove_column(column_to_remove.column_id)
        columns = session.columns.all()
        self.assertEqual(len(columns), 5)
        for index, prop_id in enumerate(['name', 'date_opened', 'opened_by_username',
                                         'last_modified', '@status']):
            self.assertEqual(columns[index].prop_id, prop_id)
            self.assertEqual(columns[index].index, index)

    def test_reorder_wrong_number_of_filter_ids_raises_error(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        filters = session.filters.all()
        new_order = [filters[1].filter_id, filters[2].filter_id]
        with self.assertRaises(ValueError):
            session.update_filter_order(new_order)

    def test_reorder_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        filters = session.filters.all()
        new_order = [
            filters[1].filter_id,
            filters[0].filter_id,
            filters[2].filter_id,
            filters[4].filter_id,
            filters[3].filter_id,
        ]
        session.update_filter_order(new_order)
        reordered_prop_ids = [c.prop_id for c in session.filters.all()]
        self.assertEqual(
            reordered_prop_ids,
            ['name', 'watered_on', 'num_leaves', 'height_cm', 'pot_type']
        )

    def test_reorder_wrong_number_of_column_ids_raises_error(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        columns = session.columns.all()
        new_order = [columns[1].column_id, columns[2].column_id]
        with self.assertRaises(ValueError):
            session.update_column_order(new_order)

    def test_update_column_order(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        columns = session.columns.all()
        new_order = [
            columns[1].column_id,
            columns[0].column_id,
            columns[2].column_id,
            columns[4].column_id,
            columns[5].column_id,
            columns[3].column_id,
        ]
        session.update_column_order(new_order)
        reordered_prop_ids = [c.prop_id for c in session.columns.all()]
        self.assertEqual(
            reordered_prop_ids,
            ['owner_name', 'name', 'date_opened', 'last_modified', '@status', 'opened_by_username']
        )

    def test_get_queryset_multiple_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
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
            .exists('watered_on')
            .empty('pot_type')
            .xpath_query(
                self.domain_name,
                "phonetic-match(name, 'lowkey') and num_leaves > 2 and height_cm <= 11.1"
            )
            .OR(all_project_data_filter(self.domain_name, ['project_data']))  # default Case Owners pinned filter
        )
        self.assertEqual(query.es_query, expected_query.es_query)

    def test_get_queryset_filters_no_xpath(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .exists('watered_on')
            .OR(all_project_data_filter(self.domain_name, ['project_data']))  # default Case Owners pinned filter
        )
        self.assertEqual(query.es_query, expected_query.es_query)

    def test_get_queryset_filters_xpath_only(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .xpath_query(
                self.domain_name,
                "num_leaves > 2"
            )
            .OR(all_project_data_filter(self.domain_name, ['project_data']))  # default Case Owners pinned filter
        )
        self.assertEqual(query.es_query, expected_query.es_query)

    def test_has_filters_and_reset(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        self.assertFalse(session.has_filters)
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        self.assertTrue(session.has_filters)
        session.reset_filters()
        self.assertFalse(session.has_filters)

    def test_has_pinned_values_and_reset(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        self.assertFalse(session.has_pinned_values)
        pinned_filter = session.pinned_filters.all()[0]
        pinned_filter.value = ['t__1']
        pinned_filter.save()
        self.assertTrue(session.has_pinned_values)
        session.reset_pinned_filters()
        self.assertFalse(session.has_pinned_values)

    def test_has_any_filtering_and_reset(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        self.assertFalse(session.has_any_filtering)
        pinned_filter = session.pinned_filters.all()[0]
        pinned_filter.value = ['t__1']
        pinned_filter.save()
        self.assertTrue(session.has_any_filtering)
        session.reset_filtering()
        self.assertFalse(session.has_any_filtering)
        session.add_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        self.assertTrue(session.has_any_filtering)
        session.reset_filtering()
        self.assertFalse(session.has_any_filtering)


class BulkEditSessionCaseColumnTests(TestCase):
    domain_name = 'session-test-case-columns'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(
            cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None
        )
        cls.django_user = User.objects.get(username=cls.web_user.username)
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

        cls.case_type = 'plant-friend'

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        self.session = BulkEditSession.new_case_session(
            self.django_user, self.domain_name, self.case_type
        )

    def test_add_column(self):
        self.assertEqual(self.session.columns.count(), 6)
        new_column = self.session.add_column('num_leaves', "Number of Leaves", DataType.INTEGER)
        self.assertEqual(new_column.index, 6)
        self.assertEqual(self.session.columns.count(), 7)
        self.assertEqual(new_column.prop_id, 'num_leaves')
        self.assertEqual(new_column.label, "Number of Leaves")
        self.assertEqual(new_column.data_type, DataType.INTEGER)
        self.assertFalse(new_column.is_system)

    def test_add_system_column(self):
        new_column = self.session.add_column('@owner_id', "Owner ID", DataType.INTEGER)
        self.assertEqual(new_column.index, 6)
        self.assertEqual(self.session.columns.count(), 7)
        self.assertEqual(new_column.prop_id, '@owner_id')
        self.assertEqual(new_column.label, "Owner ID")
        self.assertEqual(new_column.data_type, DataType.TEXT)
        self.assertTrue(new_column.is_system)
