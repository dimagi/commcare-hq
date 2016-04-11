from django.test import TestCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed import document_types
from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document
from corehq.apps.change_feed.producer import producer
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import DomainES
from corehq.pillows.domain import DomainPillow, get_domain_kafka_to_elasticsearch_pillow
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from elasticsearch.exceptions import ConnectionError
from pillowtop.es_utils import get_index_info_from_pillow, initialize_index
from pillowtop.feed.interface import Change, ChangeMeta
from testapps.test_pillowtop.utils import get_current_kafka_seq


class DomainPillowTest(TestCase):
    dependent_apps = [
        'django_prbac',
        'corehq.apps.accounting',
        'corehq.apps.domain',
        'corehq.apps.tzmigration'
    ]

    def setUp(self):
        with trap_extra_setup(ConnectionError):
            pillow = DomainPillow(online=False)
        self.index_info = get_index_info_from_pillow(pillow)
        self.elasticsearch = pillow.get_es_new()
        delete_all_domains()
        ensure_index_deleted(self.index_info.index)
        initialize_index(self.elasticsearch, self.index_info)

    def tearDown(self):
        ensure_index_deleted(self.index_info.index)

    def test_domain_pillow(self):
        # make a domain
        domain_name = 'domain-pillowtest'
        with drop_connected_signals(commcare_domain_post_save):
            create_domain(domain_name)

        # send to elasticsearch
        pillow = DomainPillow()
        pillow.process_changes(since=0, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)

        # verify there
        self._verify_domain_in_es(domain_name)

    def test_kafka_domain_pillow(self):
        # make a domain
        domain_name = 'domain-pillowtest-kafka'
        with drop_connected_signals(commcare_domain_post_save):
            domain = create_domain(domain_name)

        # send to kafka
        since = get_current_kafka_seq(document_types.DOMAIN)
        producer.send_change(document_types.DOMAIN, domain_to_change(domain).metadata)

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since={document_types.DOMAIN: since}, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)

        # verify there
        self._verify_domain_in_es(domain_name)

    def _verify_domain_in_es(self, domain_name):
        results = DomainES().run()
        self.assertEqual(1, results.total)
        domain_doc = results.hits[0]
        self.assertEqual(domain_name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])


def domain_to_change(domain):
    domain_doc = domain.to_json()
    doc_info = get_doc_meta_object_from_document(domain_doc)
    return Change(
        id=domain_doc['_id'],
        sequence_id='0',
        document=domain_doc,
        metadata=ChangeMeta(
            document_id=domain_doc['_id'],
            data_source_type=data_sources.COUCH,
            data_source_name=Domain.get_db().dbname,
            document_type=doc_info.raw_doc_type,
            document_subtype=doc_info.subtype,
            domain=domain_doc['name'],
            is_deletion=False,
        )
    )
