from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.es.users import user_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.util.es.testing import sync_users_to_es


@es_test(requires=[user_adapter], setup_class=True)
class TestUserES(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-user-es'
        cls.domain_obj = create_domain(cls.domain)

        with sync_users_to_es():
            cls._create_mobile_worker('stark', user_data={'sigil': 'direwolf', 'seat': 'Winterfell'})
            cls._create_mobile_worker('lannister', user_data={'sigil': 'lion', 'seat': 'Casterly Rock'})
            cls._create_mobile_worker('targaryen', user_data={'sigil': 'dragon', 'false_sigil': 'direwolf'})
        manager.index_refresh(user_adapter.index_name)

    @classmethod
    def _create_mobile_worker(cls, username, user_data):
        CommCareUser.create(
            domain=cls.domain,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
            user_data=user_data,
        )

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_basic_user_data_query(self):
        direwolf_families = UserES().user_data('sigil', 'direwolf').values_list('username', flat=True)
        self.assertEqual(direwolf_families, ['stark'])

    def test_chained_user_data_queries_where_both_match(self):
        direwolf_families = (UserES()
                             .user_data('sigil', 'direwolf')
                             .user_data('seat', 'Winterfell')
                             .values_list('username', flat=True))
        self.assertEqual(direwolf_families, ['stark'])

    def test_chained_user_data_queries_with_only_one_match(self):
        direwolf_families = (UserES()
                             .user_data('sigil', 'direwolf')
                             .user_data('seat', 'Casterly Rock')
                             .values_list('username', flat=True))
        self.assertEqual(direwolf_families, [])
