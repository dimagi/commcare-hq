from django.test import TestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.testing import sync_users_to_es


@es_test
class TestUserES(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.elasticsearch = get_es_new()
        initialize_index_and_mapping(cls.elasticsearch, USER_INDEX_INFO)
        cls.domain = 'test-user-es'
        cls.domain_obj = create_domain(cls.domain)

        with sync_users_to_es():
            cls._create_mobile_worker('stark', metadata={'sigil': 'direwolf', 'seat': 'Winterfell'})
            cls._create_mobile_worker('lannister', metadata={'sigil': 'lion', 'seat': 'Casterly Rock'})
            cls._create_mobile_worker('targaryen', metadata={'sigil': 'dragon', 'false_sigil': 'direwolf'})
        cls.elasticsearch.indices.refresh(USER_INDEX)

    @classmethod
    def _create_mobile_worker(cls, username, metadata):
        CommCareUser.create(
            domain=cls.domain,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
            metadata=metadata,
        )

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain_obj.delete()
        ensure_index_deleted(USER_INDEX)
        super().tearDownClass()

    def test_basic_metadata_query(self):
        direwolf_families = UserES().metadata('sigil', 'direwolf').values_list('username', flat=True)
        self.assertEqual(direwolf_families, ['stark'])

    def test_chained_metadata_queries_where_both_match(self):
        direwolf_families = (UserES()
                             .metadata('sigil', 'direwolf')
                             .metadata('seat', 'Winterfell')
                             .values_list('username', flat=True))
        self.assertEqual(direwolf_families, ['stark'])

    def test_chained_metadata_queries_with_only_one_match(self):
        direwolf_families = (UserES()
                             .metadata('sigil', 'direwolf')
                             .metadata('seat', 'Casterly Rock')
                             .values_list('username', flat=True))
        self.assertEqual(direwolf_families, [])
