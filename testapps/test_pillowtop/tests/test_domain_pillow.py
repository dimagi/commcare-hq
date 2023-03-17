from unittest.mock import patch

from django.test import TestCase

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain, publish_domain_saved
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import DomainES
from corehq.apps.es.client import manager
from corehq.apps.es.domains import domain_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.pillows.domain import get_domain_kafka_to_elasticsearch_pillow
from corehq.util.context_managers import drop_connected_signals


@es_test(requires=[domain_adapter])
class DomainPillowTest(TestCase):

    def setUp(self):
        super(DomainPillowTest, self).setUp()
        delete_all_domains()

    def test_kafka_domain_pillow(self):
        # make a domain
        domain_name = 'domain-pillowtest-kafka'
        with drop_connected_signals(commcare_domain_post_save):
            domain = create_domain(domain_name)

        # send to kafka
        since = get_topic_offset(topics.DOMAIN)
        publish_domain_saved(domain)

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(domain_adapter.index_name)

        # verify there
        self._verify_domain_in_es(domain_name)

    def test_kafka_domain_pillow_deletions(self):
        # run the other test to ensure domain is created and in ES
        self.test_kafka_domain_pillow()
        domain_obj = Domain.get_by_name('domain-pillowtest-kafka')
        domain_obj.doc_type = 'Domain-DUPLICATE'
        domain_obj.save()

        # send to kafka
        since = get_topic_offset(topics.DOMAIN)
        publish_domain_saved(domain_obj)

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(domain_adapter.index_name)

        # ensure removed from ES
        self.assertEqual(0, DomainES().run().total)

    def test_reverted_domain_pillow_deletion(self):
        domain_name = 'domain-pillow-delete'
        with drop_connected_signals(commcare_domain_post_save):
            domain = create_domain(domain_name)

        # send to kafka
        since = get_topic_offset(topics.DOMAIN)
        publish_domain_saved(domain)

        # send to elasticsearch
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(domain_adapter.index_name)

        # verify there
        self._verify_domain_in_es(domain_name)

        domain_obj = Domain.get_by_name(domain_name)
        domain_obj.doc_type = 'Domain-DUPLICATE'
        domain_obj.save()

        # send to kafka
        since = get_topic_offset(topics.DOMAIN)
        publish_domain_saved(domain_obj)

        # undelete
        domain_obj = Domain.get_by_name(domain_name)
        domain_obj.doc_type = 'Domain'
        domain_obj.save()

        # process pillow changes
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(domain_adapter.index_name)

        # confirm domain still exists
        self._verify_domain_in_es(domain_name)

    @patch('pillowtop.pillow.interface.PillowBase._update_checkpoint')
    @patch('corehq.pillows.domain.KafkaChangeFeed.iter_changes', return_value=[])
    def test_no_changes(self, mock_iter, mock_update):
        since = get_topic_offset(topics.DOMAIN)
        pillow = get_domain_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since=since, forever=True)
        self.assertFalse(mock_update.called)

    def _verify_domain_in_es(self, domain_name):
        results = DomainES().run()
        self.assertEqual(1, results.total)
        domain_doc = results.hits[0]
        self.assertEqual(domain_name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])
