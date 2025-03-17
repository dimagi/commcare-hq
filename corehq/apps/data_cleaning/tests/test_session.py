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
        self.assertEqual(new_session.column_filters.count(), 0)
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

    def test_add_column_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_column_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_column_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_column_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        column_filters = session.column_filters.all()
        for index, prop_id in enumerate(['watered_on', 'name', 'num_leaves', 'pot_type', 'height_cm']):
            self.assertEqual(column_filters[index].prop_id, prop_id)
            self.assertEqual(column_filters[index].index, index)

    def test_remove_column_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_column_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_column_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_column_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        filter_to_remove = session.column_filters.all()[1]  # name
        self.assertEqual(filter_to_remove.prop_id, 'name')
        session.remove_column_filter(filter_to_remove.filter_id)
        column_filters = session.column_filters.all()
        self.assertEqual(len(column_filters), 4)
        for index, prop_id in enumerate(['watered_on', 'num_leaves', 'pot_type', 'height_cm']):
            self.assertEqual(column_filters[index].prop_id, prop_id)
            self.assertEqual(column_filters[index].index, index)

    def test_reorder_wrong_number_of_filter_ids_raises_error(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_column_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_column_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_column_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        column_filters = session.column_filters.all()
        new_order = [column_filters[1].filter_id, column_filters[2].filter_id]
        with self.assertRaises(ValueError):
            session.reorder_column_filters(new_order)

    def test_reorder_column_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_column_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, "lowkey")
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, "2")
        session.add_column_filter('pot_type', DataType.DATE, FilterMatchType.IS_EMPTY)
        session.add_column_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, "11.0")
        column_filters = session.column_filters.all()
        new_order = [
            column_filters[1].filter_id,
            column_filters[0].filter_id,
            column_filters[2].filter_id,
            column_filters[4].filter_id,
            column_filters[3].filter_id,
        ]
        session.reorder_column_filters(new_order)
        reordered_prop_ids = [c.prop_id for c in session.column_filters.all()]
        self.assertEqual(
            reordered_prop_ids,
            ['name', 'watered_on', 'num_leaves', 'height_cm', 'pot_type']
        )

    def test_get_queryset_multiple_column_filters(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        session.add_column_filter('name', DataType.TEXT, FilterMatchType.PHONETIC, 'lowkey')
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
        session.add_column_filter('pot_type', DataType.MULTIPLE_OPTION, FilterMatchType.IS_EMPTY)
        session.add_column_filter('height_cm', DataType.DECIMAL, FilterMatchType.LESS_THAN_EQUAL, '11.1')
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

    def test_get_queryset_column_filters_no_xpath(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('watered_on', DataType.DATE, FilterMatchType.IS_NOT_MISSING)
        query = session.get_queryset()
        expected_query = (
            CaseSearchES()
            .domain(self.domain_name)
            .case_type(self.case_type)
            .exists('watered_on')
            .OR(all_project_data_filter(self.domain_name, ['project_data']))  # default Case Owners pinned filter
        )
        self.assertEqual(query.es_query, expected_query.es_query)

    def test_get_queryset_column_filters_xpath_only(self):
        session = BulkEditSession.new_case_session(self.django_user, self.domain_name, self.case_type)
        session.add_column_filter('num_leaves', DataType.INTEGER, FilterMatchType.GREATER_THAN, '2')
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
