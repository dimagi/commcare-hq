import uuid

from django.test import Client, TestCase
from django.urls import reverse

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
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@es_test(requires=[case_search_adapter])
class CleanCasesViewAccessTest(TestCase):
    domain_name = 'clean-data-view-test'
    other_domain_name = 'no-access-view-test'
    password = 'Passw0rd!'
    fake_session_id = uuid.uuid4()
    all_views = [
        (CleanCasesMainView, (domain_name,)),
        (SetupCaseSessionFormView, (domain_name,)),
        (CaseCleaningTasksTableView, (domain_name,)),
        (CleanCasesSessionView, (domain_name, fake_session_id,)),
        (CleanCasesTableView, (domain_name, fake_session_id,)),
    ]

    @classmethod
    def make_user(cls, email, domain_obj):
        user = WebUser.create(
            domain=domain_obj.name,
            username=email,
            password=cls.password,
            created_by=None,
            created_via=None
        )
        user.save()
        return user

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.other_domain_obj = create_domain(cls.other_domain_name)

        cls.user_in_domain = cls.make_user(
            'domain_member@datacleaning.org',
            cls.domain_obj,
        )
        cls.user_outside_of_domain = cls.make_user(
            'outsider@nope.org',
            cls.other_domain_obj,
        )
        cls.client = Client()

    @classmethod
    def tearDownClass(cls):
        cls.user_in_domain.delete(cls.domain_name, deleted_by=None)
        cls.user_outside_of_domain.delete(cls.other_domain_obj, deleted_by=None)
        cls.domain_obj.delete()
        cls.other_domain_obj.delete()
        super().tearDownClass()

    def test_has_no_access_without_login(self):
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                404,
                msg=f"{view_class.__name__} should NOT be accessible"
            )

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

    @flag_enabled('DATA_CLEANING_CASES')
    def test_has_access_with_flag(self):
        """
        Todo: update the access tests to include project privilege
        and user permissions/roles once specifics are decided.
        """
        self.client.login(username=self.user_in_domain.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                msg=f"{view_class.__name__} should be accessible"
            )

    @flag_enabled('DATA_CLEANING_CASES')
    def test_has_no_access_with_other_domain(self):
        self.client.login(username=self.user_outside_of_domain.username, password=self.password)
        for view_class, args in self.all_views:
            url = reverse(view_class.urlname, args=args)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                404,
                msg=f"{view_class.__name__} should NOT be accessible"
            )
