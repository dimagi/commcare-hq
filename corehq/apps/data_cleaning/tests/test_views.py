import uuid

from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)
from corehq.apps.data_cleaning.utils.cases import clear_caches_case_data_cleaning
from corehq.apps.data_cleaning.views.columns import (
    ManageColumnsFormView,
)
from corehq.apps.data_cleaning.views.filters import (
    PinnedFilterFormView,
    ManageFiltersFormView,
)
from corehq.apps.data_cleaning.views.main import (
    CleanCasesMainView,
    CleanCasesSessionView,
)
from corehq.apps.data_cleaning.views.tables import (
    CleanCasesTableView,
    CaseCleaningTasksTableView,
)
from corehq.apps.data_cleaning.views.setup import (
    SetupCaseSessionFormView,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import group_adapter
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.privileges import BULK_DATA_CLEANING
from corehq.util.test_utils import flag_enabled, privilege_enabled


@es_test(requires=[case_search_adapter, user_adapter, group_adapter], setup_class=True)
class CleanCasesViewAccessTest(TestCase):
    domain_name = 'clean-data-view-test'
    other_domain_name = 'no-access-view-test'
    password = 'Passw0rd!'

    @classmethod
    def make_user(cls, email, domain_obj, role):
        user = WebUser.create(
            domain=domain_obj.name,
            username=email,
            password=cls.password,
            role_id=role.get_id,
            created_by=None,
            created_via=None,
        )
        user.save()
        return user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.other_domain_obj = create_domain(cls.other_domain_name)

        role_with_permission = UserRole.create(
            cls.domain_name, 'can-edit-data', permissions=HqPermissions(edit_data=True)
        )
        role_without_permission = UserRole.create(
            cls.domain_name, 'cannot-do-anything', permissions=HqPermissions()
        )

        cls.user_in_domain = cls.make_user(
            'domain_member@datacleaning.org',
            cls.domain_obj,
            role_with_permission,
        )
        cls.user_without_role = cls.make_user(
            'domain_member_junior@datacleaning.org',
            cls.domain_obj,
            role_without_permission,
        )
        cls.user_outside_of_domain = cls.make_user(
            'outsider@nope.org',
            cls.other_domain_obj,
            role_with_permission,
        )
        cls.client = Client()
        session = BulkEditSession.new_case_session(
            cls.user_in_domain.get_django_user(), cls.domain_name, 'plants',
        )
        cls.real_session_id = session.session_id
        cls.fake_session_id = uuid.uuid4()
        cls.all_views = [
            (CleanCasesMainView, (cls.domain_name,)),
            (SetupCaseSessionFormView, (cls.domain_name,)),
            (CaseCleaningTasksTableView, (cls.domain_name,)),
            (CleanCasesSessionView, (cls.domain_name, cls.real_session_id,)),
            (CleanCasesSessionView, (cls.domain_name, cls.fake_session_id,)),
            (CleanCasesTableView, (cls.domain_name, cls.real_session_id,)),
            (CleanCasesTableView, (cls.domain_name, cls.fake_session_id,)),
            (PinnedFilterFormView, (cls.domain_name, cls.real_session_id,)),
            (PinnedFilterFormView, (cls.domain_name, cls.fake_session_id,)),
            (ManageFiltersFormView, (cls.domain_name, cls.real_session_id,)),
            (ManageFiltersFormView, (cls.domain_name, cls.fake_session_id,)),
            (ManageColumnsFormView, (cls.domain_name, cls.real_session_id,)),
            (ManageColumnsFormView, (cls.domain_name, cls.fake_session_id,)),
        ]
        cls.views_not_found_with_invalid_session = [
            CleanCasesTableView,
            PinnedFilterFormView,
            ManageFiltersFormView,
            ManageColumnsFormView,
        ]

        clear_caches_case_data_cleaning(cls.domain_name)

    @classmethod
    def tearDownClass(cls):
        cls.user_in_domain.delete(cls.domain_name, deleted_by=None)
        cls.user_outside_of_domain.delete(cls.other_domain_obj, deleted_by=None)
        cls.user_without_role.delete(cls.domain_name, deleted_by=None)
        cls.domain_obj.delete()
        cls.other_domain_obj.delete()
        super().tearDownClass()

    @privilege_enabled(BULK_DATA_CLEANING)
    def test_has_no_access_without_login(self):
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                403,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

    @privilege_enabled(BULK_DATA_CLEANING)
    def test_has_no_access_without_flag(self):
        self.client.login(username=self.user_in_domain.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                404,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

    def test_has_no_access_without_privilege(self):
        self.client.login(username=self.user_in_domain.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                403,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

    @privilege_enabled(BULK_DATA_CLEANING)
    def test_has_no_access_without_permission(self):
        self.client.login(username=self.user_without_role.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                403,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

    @privilege_enabled(BULK_DATA_CLEANING)
    @flag_enabled('DATA_CLEANING_CASES')
    def test_has_access_with_prereqs(self):
        self.client.login(username=self.user_in_domain.username, password=self.password)
        for view_class, args in self.all_views:
            if self.fake_session_id in args:
                # only test real sessions
                continue
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                msg=f"{view_class.__name__} should be accessible"
            )

    @privilege_enabled(BULK_DATA_CLEANING)
    @flag_enabled('DATA_CLEANING_CASES')
    def test_redirects_session_with_no_existing_session(self):
        self.client.login(username=self.user_in_domain.username, password=self.password)
        session_url = reverse(CleanCasesSessionView.urlname, args=(self.domain_name, self.fake_session_id))
        response = self.client.get(session_url)
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(BULK_DATA_CLEANING)
    @flag_enabled('DATA_CLEANING_CASES')
    def test_views_not_found_with_invalid_session(self):
        self.client.login(username=self.user_in_domain.username, password=self.password)

        for view_class, args in self.all_views:
            if not (self.fake_session_id in args
                    and view_class in self.views_not_found_with_invalid_session):
                # only test views expected to 404 with invalid sessions
                continue
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                404,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

    @privilege_enabled(BULK_DATA_CLEANING)
    @flag_enabled('DATA_CLEANING_CASES')
    def test_has_no_access_with_other_domain(self):
        self.client.login(username=self.user_outside_of_domain.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                403,
                msg=f"{view_class.__name__} should NOT be accessible"
            )
