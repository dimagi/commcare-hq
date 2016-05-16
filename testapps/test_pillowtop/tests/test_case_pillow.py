import uuid
from django.test import TestCase, override_settings
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.es import CaseES
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case import CasePillow, get_sql_case_to_elasticsearch_pillow
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_case
from elasticsearch.exceptions import ConnectionError
from testapps.test_pillowtop.utils import get_test_kafka_consumer


class CasePillowTest(TestCase):

    domain = 'case-pillowtest-domain'

    def setUp(self):
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.pillow = CasePillow()
        self.elasticsearch = self.pillow.get_es_new()
        delete_es_index(self.pillow.es_index)

    def tearDown(self):
        ensure_index_deleted(self.pillow.es_index)

    def test_case_pillow_couch(self):
        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case(self.domain, case_id, case_name)

        # send to elasticsearch
        self._sync_couch_cases_to_es()

        # verify there
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

        # cleanup
        case.delete()

    def test_case_soft_deletion(self):
        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case(self.domain, case_id, case_name)

        # send to elasticsearch
        self._sync_couch_cases_to_es()

        # verify there
        results = CaseES().run()
        self.assertEqual(1, results.total)

        seq_before_deletion = self.pillow.get_change_feed().get_latest_change_id()

        # soft delete the case
        case.soft_delete()

        # sync to elasticsearch
        self._sync_couch_cases_to_es(since=seq_before_deletion)

        # ensure not there anymore
        results = CaseES().run()
        self.assertEqual(0, results.total)

        # cleanup
        case.delete()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_case_pillow_sql(self):
        consumer = get_test_kafka_consumer(topics.CASE_SQL)
        # have to get the seq id before the change is processed
        kafka_seq = consumer.offsets()['fetch'][(topics.CASE_SQL, 0)]

        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case(self.domain, case_id, case_name)

        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        sql_pillow = get_sql_case_to_elasticsearch_pillow()
        sql_pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(self.pillow.es_index)

        # confirm change made it to elasticserach
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    def _sync_couch_cases_to_es(self, since=0):
        self.pillow.process_changes(since=since, forever=False)
        self.elasticsearch.indices.refresh(self.pillow.es_index)
