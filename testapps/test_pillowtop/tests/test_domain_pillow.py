from django.test import TestCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed import document_types
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import DomainES
from corehq.elastic import get_es_new
from corehq.pillows.domain import get_domain_kafka_to_elasticsearch_pillow
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index
from testapps.test_pillowtop.utils import get_current_kafka_seq


class DomainPillowTest(TestCase):
    dependent_apps = [
        'django_prbac',
        'corehq.apps.accounting',
        'corehq.apps.domain',
        'corehq.apps.tzmigration'
    ]

    def setUp(self):
        self.index_info = DOMAIN_INDEX_INFO
        self.elasticsearch = get_es_new()
        delete_all_domains()
        ensure_index_deleted(self.index_info.index)
        initialize_index(self.elasticsearch, self.index_info)

    def tearDown(self):
        ensure_index_deleted(self.index_info.index)

    def test_kafka_domain_pillow(self):
        # make a domain
        domain_name = 'domain-pillowtest-kafka'
        with drop_connected_signals(commcare_domain_post_save):
            domain = create_domain(domain_name)

        # send to kafka
        since = get_current_kafka_seq(document_types.DOMAIN)
        producer.send_change(document_types.DOMAIN, _domain_to_change_meta(domain))

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since={document_types.DOMAIN: since}, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)

        # verify there
        self._verify_domain_in_es(domain_name)

    def test_kafka_domain_pillow_deletions(self):
        # run the other test to ensure domain is created and in ES
        self.test_kafka_domain_pillow()
        domain_obj = Domain.get_by_name('domain-pillowtest-kafka')
        domain_obj.doc_type = 'Domain-DUPLICATE'

        # send to kafka
        since = get_current_kafka_seq(document_types.DOMAIN)
        producer.send_change(document_types.DOMAIN, _domain_to_change_meta(domain_obj))

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since={document_types.DOMAIN: since}, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)

        # ensure removed from ES
        self.assertEqual(0, DomainES().run().total)

    def _verify_domain_in_es(self, domain_name):
        results = DomainES().run()
        self.assertEqual(1, results.total)
        domain_doc = results.hits[0]
        self.assertEqual(domain_name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])


def _domain_to_change_meta(domain):
    domain_doc = domain.to_json()
    return change_meta_from_doc(
        document=domain_doc,
        data_source_type=data_sources.COUCH,
        data_source_name=Domain.get_db().dbname,
    )
