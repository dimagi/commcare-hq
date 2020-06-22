import uuid

from django.test import override_settings, TestCase
from mock import MagicMock, patch

from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.case_search.exceptions import CaseSearchNotEnabledException
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    change_meta_from_kafka_message,
)
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_multi_topic_offset
from corehq.apps.es import CaseSearchES
from corehq.apps.userreports.tests.utils import doc_to_change
from corehq.apps.es.case_search import case_property_missing
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case import get_case_pillow
from corehq.pillows.case_search import (
    CaseSearchReindexerFactory,
    delete_case_search_cases,
    domains_needing_search_index,
)
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX,
    CASE_SEARCH_INDEX_INFO,
)
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_and_save_a_case
from nose.plugins.attrib import attr
from pillowtop.es_utils import initialize_index_and_mapping


@attr(es_test=True)
class CaseSearchPillowTest(TestCase):

    domain = 'meereen'

    def setUp(self):
        super(CaseSearchPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        self.elasticsearch = get_es_new()
        self.pillow = get_case_pillow(skip_ucr=True)
        ensure_index_deleted(CASE_SEARCH_INDEX)

        # Bootstrap ES
        initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        CaseSearchConfig.objects.all().delete()
        super(CaseSearchPillowTest, self).tearDown()

    def test_case_search_pillow(self):
        consumer = get_test_kafka_consumer(topics.CASE)
        kafka_seq = self._get_kafka_seq()

        case = self._make_case(case_properties={'foo': 'bar'})
        producer.send_change(topics.CASE, doc_to_change(case.to_json()).metadata)
        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # enable case search for domain
        with patch('corehq.pillows.case_search.domain_needs_search_index',
                   new=MagicMock(return_value=True)) as fake_case_search_enabled_for_domain:
            # send to elasticsearch
            self.pillow.process_changes(since=kafka_seq, forever=False)
            fake_case_search_enabled_for_domain.assert_called_with(self.domain)

        self._assert_case_in_es(self.domain, case)

    def test_case_search_reindex_by_domain(self):
        """
        Tests reindexing for a particular domain only
        """
        other_domain = "yunkai"
        CaseSearchConfig.objects.get_or_create(pk=other_domain, enabled=True)
        domains_needing_search_index.clear()

        desired_case = self._make_case(domain=other_domain)
        undesired_case = self._make_case(domain=self.domain)  # noqa

        with self.assertRaises(CaseSearchNotEnabledException):
            CaseSearchReindexerFactory(domain=self.domain).build().reindex()

        CaseSearchReindexerFactory(domain=other_domain).build().reindex()
        self._assert_case_in_es(other_domain, desired_case)

    def test_delete_case_search_cases(self):
        """
        Tests that cases are correctly removed from the es index
        """
        other_domain = "braavos"
        self._bootstrap_cases_in_es_for_domain(self.domain)
        case = self._bootstrap_cases_in_es_for_domain(other_domain)

        with self.assertRaises(TypeError):
            delete_case_search_cases(None)
        with self.assertRaises(TypeError):
            delete_case_search_cases({})

        # delete cases from one domain
        delete_case_search_cases(self.domain)

        # make sure the other domain's cases are still there
        self._assert_case_in_es(other_domain, case)

        # delete other domains cases
        delete_case_search_cases(other_domain)

        # make sure nothing is left
        self._assert_index_empty()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_sql_case_search_pillow(self):
        consumer = get_test_kafka_consumer(topics.CASE_SQL)
        # have to get the seq id before the change is processed
        kafka_seq = self._get_kafka_seq()
        case = self._make_case(case_properties={'something': 'something_else'})

        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # enable case search for domain
        with patch('corehq.pillows.case_search.domain_needs_search_index',
                   new=MagicMock(return_value=True)) as fake_case_search_enabled_for_domain:
            # send to elasticsearch
            self.pillow.process_changes(since=kafka_seq, forever=False)
            fake_case_search_enabled_for_domain.assert_called_with(self.domain)

        self._assert_case_in_es(self.domain, case)

    def _get_kafka_seq(self):
        # KafkaChangeFeed listens for multiple topics (case, case-sql) in the case search pillow,
        # so we need to provide a dict of seqs to kafka
        return get_multi_topic_offset([topics.CASE, topics.CASE_SQL])

    def _make_case(self, domain=None, case_properties=None):
        # make a case
        case_properties = case_properties or {}
        if '_id' in case_properties:
            case_id = case_properties.pop('_id')
        else:
            case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        if domain is None:
            domain = self.domain
        if 'owner_id' in case_properties:
            owner_id = case_properties.pop('owner_id')
        else:
            owner_id = None
        case = create_and_save_a_case(domain, case_id, case_name, case_properties, owner_id=owner_id)
        return case

    def _assert_case_in_es(self, domain, case):
        # confirm change made it to elasticserach
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)
        results = CaseSearchES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]

        self.assertEqual(domain, case_doc['domain'])
        self.assertEqual(case.case_id, case_doc['_id'])
        self.assertEqual(case.name, case_doc['name'])
        # Confirm change contains case_properties
        self.assertItemsEqual(list(case_doc['case_properties'][0]), ['key', 'value'])
        for case_property in case_doc['case_properties']:
            key = case_property['key']
            try:
                self.assertEqual(
                    SPECIAL_CASE_PROPERTIES_MAP[key].value_getter(case.to_json()),
                    case_property['value'],
                )
            except KeyError:
                self.assertEqual(case.get_case_property(key), case_property['value'])

    def _assert_index_empty(self):
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)
        results = CaseSearchES().run()
        self.assertEqual(0, results.total)

    def _bootstrap_cases_in_es_for_domain(self, domain, create_case=True):
        case = self._make_case(domain) if create_case else None
        with patch('corehq.pillows.case_search.domains_needing_search_index',
                   MagicMock(return_value=[domain])):
            CaseSearchReindexerFactory(domain=domain).build().reindex()
        return case

    def _assert_query_runs_correctly(self, domain, input_cases, query, output):
        for case in input_cases:
            self._make_case(domain, case)
        self._bootstrap_cases_in_es_for_domain(domain, create_case=False)
        self.elasticsearch.indices.refresh(CASE_SEARCH_INDEX)
        self.assertItemsEqual(
            query.get_ids(),
            output
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_simple_case_property_query(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard'},
                {'_id': 'c2', 'name': 'blackbeard'},
            ],
            CaseSearchES().domain(self.domain).case_property_query("name", "redbeard"),
            ['c1']
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_multiple_case_search_queries(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("name", "redbeard")
                 .case_property_query("parrot_name", "polly"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'name': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'name': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            ['c1']
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_multiple_case_search_queries_should_clause(self):
        query = (CaseSearchES().domain(self.domain)
                 .case_property_query("name", "redbeard")
                 .case_property_query("parrot_name", "polly", clause="should"))
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'name': 'redbeard', 'parrot_name': 'polly'},
                {'_id': 'c2', 'name': 'blackbeard', 'parrot_name': 'polly'},
                {'_id': 'c3', 'name': 'redbeard', 'parrot_name': 'molly'}
            ],
            query,
            ['c1', 'c3']
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_blacklisted_owner_ids(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'owner_id': '123'},
                {'_id': 'c2', 'owner_id': '234'},
            ],
            CaseSearchES().domain(self.domain).blacklist_owner_id('123'),
            ['c2']
        )

    def test_missing_case_property(self):
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c2', 'name': 'blackbeard'},
                {'_id': 'c3', 'name': ''},
                {'_id': 'c4'},
            ],
            CaseSearchES().domain(self.domain).filter(case_property_missing('name')),
            ['c3'] # todo; flag farid
        )
