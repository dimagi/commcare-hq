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
from corehq.apps.users.models import WebUser


class BulkEditSessionTest(TestCase):
    domain_name = 'dc-session-test'
    username = 'someone@cleandata.org'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(
            cls.domain.name, 'b@vaultwax.com', 'testpwd', None, None
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


class BulkEditSessionFilteredQuerysetTests(TestCase):
    domain_name = 'session-test-queryset'

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
