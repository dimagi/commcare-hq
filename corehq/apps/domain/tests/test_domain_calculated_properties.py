from __future__ import print_function, unicode_literals
from __future__ import absolute_import
import json

from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.calculations import all_domain_stats, calced_props
from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping


class DomainCalculatedPropertiesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DomainCalculatedPropertiesTest, cls).setUpClass()
        cls.es = [{
            'info': i,
            'instance': get_es_new(),
        } for i in [CASE_INDEX_INFO, SMS_INDEX_INFO, XFORM_INDEX_INFO]]

    def setUp(self):
        self.domain = Domain(name='test-b9289e19d819')
        self.domain.save()
        for es in self.es:
            ensure_index_deleted(es['info'].index)
            initialize_index_and_mapping(es['instance'], es['info'])

    def tearDown(self):
        self.domain.delete()

    def test_sanity(self):
        all_stats = all_domain_stats()
        props = calced_props(self.domain, self.domain._id, all_stats)
        self.assertFalse(props['cp_has_app'])
        # ensure serializable
        json.dumps(props)
