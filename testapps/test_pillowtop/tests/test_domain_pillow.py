from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import DomainES
from corehq.pillows.domain import DomainPillow
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from elasticsearch.exceptions import ConnectionError
from pillowtop.es_utils import get_index_info_from_pillow, initialize_index


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

    def _verify_domain_in_es(self, domain_name):
        results = DomainES().run()
        self.assertEqual(1, results.total)
        domain_doc = results.hits[0]
        self.assertEqual(domain_name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])
