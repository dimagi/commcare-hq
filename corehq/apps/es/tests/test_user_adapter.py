from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import UserES, demo_users, user_adapter
from corehq.apps.users.models import CommCareUser, WebUser


@es_test(requires=[user_adapter], setup_class=True)
class TestFromPythonInElasticUser(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-tests'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = CommCareUser.create(
            username="rock", domain=cls.domain, password="***********",
            created_by=None, created_via=None
        )
        cls.web_user = WebUser.create(
            username='webman', domain=cls.domain, password="***********",
            created_by=None, created_via=None
        )
        cls.addClassCleanup(cls.user.delete, None, None)
        cls.addClassCleanup(cls.web_user.delete, None, None)

    def test_from_python_works_with_user_objects(self):
        user_adapter.from_python(self.user)
        user_adapter.from_python(self.web_user)

    def test_from_python_works_with_user_dicts(self):
        user_adapter.from_python(self.user.to_json())
        user_adapter.from_python(self.web_user.to_json())

    def test_from_python_removes_password_field(self):
        user_obj = self.user.to_json()
        self.assertIn('password', user_obj)
        user_es_obj = user_adapter.from_python(user_obj)
        self.assertNotIn('password', user_es_obj)

    def test_from_python_works_fine_if_password_field_not_present(self):
        user_obj = self.user.to_json()
        user_obj.pop('password')
        user_es_obj = user_adapter.from_python(user_obj)
        self.assertNotIn('password', user_es_obj)

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, user_adapter.from_python, set)

    def test_index_can_handle_user_objects(self):
        user_adapter.index(self.user, refresh=True)
        self.addCleanup(user_adapter.delete, self.user._id)

        commcare_user = user_adapter.to_json(self.user)
        es_user = user_adapter.search({})['hits']['hits'][0]['_source']

        self.assertEqual(es_user, commcare_user)


@es_test(requires=[user_adapter], setup_class=True)
class TestUserFilters(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.other_domain = 'another_test-domain'
        cls.other_domain_obj = create_domain(cls.other_domain)
        cls.addClassCleanup(cls.other_domain_obj.delete)

        cls.demo_user = CommCareUser.create(
            username="demo", domain=cls.domain, password="***********", is_active=True,
            created_by=None, created_via=None
        )
        cls.demo_user.is_demo_user = True
        cls.demo_user.save()

        cls.regular_user = CommCareUser.create(
            username="regular", domain=cls.domain, password="***********", is_active=True,
            created_by=None, created_via=None
        )
        cls.regular_user.domain_membership.is_admin = True

        cls.web_user = WebUser.create(
            username="web", domain=cls.domain, password="***********", is_active=True,
            created_by=None, created_via=None
        )
        cls.web_user.get_domain_membership(cls.domain).is_admin = True
        cls.web_user.add_domain_membership(cls.other_domain)

        user_adapter.index(cls.demo_user, refresh=True)
        user_adapter.index(cls.regular_user, refresh=True)
        user_adapter.index(cls.web_user, refresh=True)
        cls.addClassCleanup(cls.demo_user.delete, None, None)
        cls.addClassCleanup(cls.regular_user.delete, None, None)
        cls.addClassCleanup(cls.web_user.delete, None, None)

    def test_demo_users_filter(self):
        es_query = UserES().domain(self.domain).filter(demo_users())
        results = es_query.run().hits

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['_id'], self.demo_user._id)

    def test_commcareuser_user_domain_membership(self):
        es_query = UserES().domain(self.domain).mobile_users().is_admin(self.domain)
        results = es_query.run().hits
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['_id'], self.regular_user._id)

    def test_web_user_domain_membership(self):
        # The web user is an admin on `domain` but not on `other_domain`
        es_query = UserES().domain(self.domain).web_users().is_admin(self.domain)
        results = es_query.run().hits
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['_id'], self.web_user._id)

        es_query = UserES().domain(self.domain).web_users().is_admin(self.other_domain)
        results = es_query.run().hits
        self.assertEqual(len(results), 0)

    def test_list_of_domains(self):
        matches = (UserES()
                   .domain([self.domain, self.other_domain])
                   .mobile_users()
                   .values_list('username', flat=True))
        self.assertItemsEqual(matches, [
            self.demo_user.username,
            self.regular_user.username
        ])
