from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
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

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, user_adapter.from_python, set)

    def test_index_can_handle_user_objects(self):
        user_adapter.index(self.user, refresh=True)
        self.addCleanup(user_adapter.delete, self.user._id)

        commcare_user = user_adapter.to_json(self.user)
        es_user = user_adapter.search({})['hits']['hits'][0]['_source']

        del commcare_user['domain_memberships']
        del es_user['domain_membership']

        self.assertEqual(es_user, commcare_user)

    def test_domain_membership_transform(self):
        user_adapter.index(self.user, refresh=True)
        es_unfixed_doc = user_adapter._search({})['hits']['hits'][0]['_source']
        self.assertTrue('domain_memberships' in es_unfixed_doc)
        es_fixed_doc = user_adapter.search({})['hits']['hits'][0]['_source']
        self.assertTrue('domain_membership' in es_fixed_doc)
