import datetime
import json

from django.test import TestCase

from corehq.apps.es.sms import SMSES
from corehq.apps.sms.models import INCOMING, OUTGOING
from dimagi.utils.parsing import json_format_datetime
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.calculations import all_domain_stats, calced_props, sms
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_instance, refresh_elasticsearch_index, get_es_interface
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.processors.elastic import send_to_elasticsearch


class DomainCalculatedPropertiesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DomainCalculatedPropertiesTest, cls).setUpClass()
        cls.es = [{
            'info': i,
            'instance': get_es_instance(),
        } for i in [CASE_INDEX_INFO, SMS_INDEX_INFO, XFORM_INDEX_INFO]]

    def setUp(self):
        self.domain = Domain(name='test-b9289e19d819')
        self.domain.save()
        for es in self.es:
            ensure_index_deleted(es['info'].index)
            initialize_index_and_mapping(es['instance'], es['info'])
        self._set_up_sms_es()

    def _set_up_sms_es(self):
        sms_doc = {
            '_id': 'some_sms_id',
            'domain': self.domain.name,
            'direction': INCOMING,
            'date': json_format_datetime(datetime.datetime.utcnow()),
            'doc_type': SMS_INDEX_INFO.type,
        }
        send_to_elasticsearch(
            index=SMS_INDEX_INFO.index,
            doc_type=SMS_INDEX_INFO.type,
            doc_id=sms_doc['_id'],
            name='ElasticProcessor',
            data=sms_doc,
            update=False,
        )
        refresh_elasticsearch_index('sms')

    def tearDown(self):
        self.domain.delete()

    def test_sanity(self):
        all_stats = all_domain_stats()
        props = calced_props(self.domain, self.domain._id, all_stats)
        self.assertFalse(props['cp_has_app'])
        # ensure serializable
        json.dumps(props)

    def test_sms(self):
        self.assertEqual(SMSES().count(), 1)
        self.assertEqual(sms(self.domain.name, INCOMING), 1)
        self.assertEqual(sms(self.domain.name, OUTGOING), 0)
