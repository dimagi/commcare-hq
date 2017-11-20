from __future__ import absolute_import
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.pillows.domain import transform_domain_for_elasticsearch


class TransformDomainForElasticsearchTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TransformDomainForElasticsearchTest, cls).setUpClass()
        cls.domain = 'domain-transform-test'
        cls.project = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        super(TransformDomainForElasticsearchTest, cls).tearDownClass()
        for snapshot in cls.project.snapshots():
            snapshot.delete()
        cls.project.delete()

    def test(self):
        counts = [8, 10, 72]
        copies = []
        for count in counts:
            copy = self.project.save_snapshot(share_reminders=False, copy_by_id=set())
            copy.downloads = count
            copy.save()
            copies.append(copy)
        for copy in copies:
            es_doc = transform_domain_for_elasticsearch(copy.to_json())
            self.assertEqual(es_doc['full_downloads'], sum(counts))
