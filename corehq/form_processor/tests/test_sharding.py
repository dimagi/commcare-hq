from collections import defaultdict
from unittest import skipUnless, SkipTest
from uuid import uuid4

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.tests.utils import create_form_for_test, FormProcessorTestUtils
from corehq.sql_db.config import PartitionConfig

DOMAIN = 'sharding-test'


@override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
@skipUnless(settings.USE_PARTITIONED_DATABASE, 'Only applicable if sharding is setup')
class ShardingTests(TestCase):

    @classmethod
    def setUpClass(cls):
        if not settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if sharding is setup')
        super(ShardingTests, cls).setUpClass()
        cls.partion_config = PartitionConfig()
        assert len(cls.partion_config.get_form_processing_dbs()) > 1

    def tearDown(self):
        FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
        FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super(ShardingTests, self).tearDown()

    def test_objects_only_in_one_db(self):
        case_id = uuid4().hex
        form = create_form_for_test(DOMAIN, case_id=case_id)

        dbs_with_form = []
        dbs_with_case = []
        for db in self.partion_config.get_form_processing_dbs():
            form_in_db = XFormInstanceSQL.objects.using(db).filter(form_id=form.form_id).exists()
            if form_in_db:
                dbs_with_form.append(db)

            case_in_db = CommCareCaseSQL.objects.using(db).filter(case_id=case_id).exists()
            if case_in_db:
                dbs_with_case.append(db)

        self.assertEqual(1, len(dbs_with_form))
        self.assertEqual(1, len(dbs_with_case))

    def test_objects_distributed_to_all_dbs(self):
        """
        Rudimentary test to ensure that not all cases / forms get saved to the same DB.
        """
        num_forms = 20
        for i in range(num_forms):
            create_form_for_test(DOMAIN, case_id=uuid4().hex)

        forms_per_db = {}
        cases_per_db = {}
        for db in self.partion_config.get_form_processing_dbs():
            forms_per_db[db] = XFormInstanceSQL.objects.using(db).filter(domain=DOMAIN).count()
            cases_per_db[db] = CommCareCaseSQL.objects.using(db).filter(domain=DOMAIN).count()

        self.assertEqual(num_forms, sum(forms_per_db.values()), forms_per_db)
        self.assertEqual(num_forms, sum(cases_per_db.values()), cases_per_db)
        self.assertTrue(
            all(num_forms_in_db < num_forms for num_forms_in_db in forms_per_db.values()),
            forms_per_db
        )
        self.assertTrue(
            all(num_cases_in_db < num_forms for num_cases_in_db in cases_per_db.values()),
            cases_per_db
        )

    def test_python_hashing_gives_correct_db(self):
        # Rudimentary test to ensure that python sharding matches SQL sharding
        num_forms = 100
        form_ids = [create_form_for_test(DOMAIN).form_id for i in range(num_forms)]

        dbs_for_docs = ShardAccessor.get_database_for_docs(form_ids)
        for form_id, db_alias in dbs_for_docs.items():
            XFormInstanceSQL.objects.using(db_alias).get(form_id=form_id)


DATABASES = {
    key: {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': key,
    } for key in ['default', 'proxy', 'p1', 'p2', 'p3', 'p4', 'p5']
}


PARTITION_DATABASE_CONFIG = {
    'shards': {
        'p1': [0, 204],
        'p2': [205, 409],
        'p3': [410, 614],
        'p4': [615, 819],
        'p5': [820, 1023]
    },
    'groups': {
        'main': ['default'],
        'proxy': ['proxy'],
        'form_processing': ['p1', 'p2', 'p3', 'p4', 'p5'],
    }
}


@override_settings(PARTITION_DATABASE_CONFIG=PARTITION_DATABASE_CONFIG, DATABASES=DATABASES, ALLOW_FORM_PROCESSING_QUERIES=True)
@skipUnless(settings.USE_PARTITIONED_DATABASE, 'Only applicable if sharding is setup')
class ShardAccessorTests(TestCase):
    def test_hash_doc_ids(self):
        N = 1001
        doc_ids = [str(i) for i in range(N)]
        hashes = ShardAccessor.hash_doc_ids(doc_ids)
        self.assertEquals(len(hashes), N)
        self.assertTrue(all(isinstance(hash_, int) for hash_ in hashes.values()))

    def test_get_database_for_docs(self):
        # test that sharding 1000 docs gives a distribution withing some tollerance
        # (bit of a vague test)
        N = 1000
        doc_ids = [str(i) for i in range(N)]
        doc_db_map = ShardAccessor.get_database_for_docs(doc_ids)
        doc_count_per_db = defaultdict(int)
        for db_alias in doc_db_map.values():
            doc_count_per_db[db_alias] += 1

        num_dbs = len(PartitionConfig().get_form_processing_dbs())
        even_split = int(N / num_dbs)
        tollerance = N * 0.05  # 5% tollerance
        diffs = [abs(even_split - count) for count in doc_count_per_db.values()]
        self.assertTrue(all(diff < tollerance for diff in diffs))

    def test_hash_in_python(self):
        # test that python hashing matches with SQL hashing
        N = 1024
        doc_ids = [str(i) for i in range(N)]

        sql_hashes = ShardAccessor.hash_doc_ids(doc_ids)

        csiphash_hashes = ShardAccessor.hash_doc_ids_python(doc_ids)
        self.assertEquals(len(csiphash_hashes), N)
        self.assertTrue(all(isinstance(hash_, (int, long)) for hash_ in csiphash_hashes.values()))

        N_shards = 1024
        part_mask = N_shards - 1

        sql_shards = {doc_id: hash_ & part_mask for doc_id, hash_ in sql_hashes.items()}
        python_shards = {doc_id: hash_ & part_mask for doc_id, hash_ in sql_hashes.items()}

        self.assertEqual(python_shards, sql_shards)
