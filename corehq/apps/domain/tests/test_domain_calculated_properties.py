import datetime
import json

from django.test import TestCase

from corehq.apps.es.sms import SMSES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.sms.models import INCOMING, OUTGOING
from dimagi.utils.parsing import json_format_datetime
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.calculations import all_domain_stats, calced_props, sms, get_sms_count
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_new, refresh_elasticsearch_index
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.elastic import send_to_elasticsearch


@es_test
class BaseCalculatedPropertiesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseCalculatedPropertiesTest, cls).setUpClass()
        cls.es = [{
            'info': index_info,
            'instance': get_es_new(),
        } for index_info in [CASE_INDEX_INFO, SMS_INDEX_INFO, XFORM_INDEX_INFO, USER_INDEX_INFO]]

        cls.domain = Domain(name='test')
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(BaseCalculatedPropertiesTest, cls).tearDownClass()

    def setUp(self):
        for es in self.es:
            ensure_index_deleted(es['info'].index)
            initialize_index_and_mapping(es['instance'], es['info'])

    @staticmethod
    def create_sms_in_es(domain_name, direction):
        sms_doc = {
            '_id': 'some_sms_id',
            'domain': domain_name,
            'direction': direction,
            'date': json_format_datetime(datetime.datetime.utcnow()),
            'doc_type': SMS_INDEX_INFO.type,
        }
        send_to_elasticsearch("sms", sms_doc)
        refresh_elasticsearch_index('sms')
        return sms_doc

    @staticmethod
    def delete_sms_in_es(sms_doc):
        send_to_elasticsearch("sms", sms_doc, delete=True)
        refresh_elasticsearch_index('sms')


class DomainCalculatedPropertiesTest(BaseCalculatedPropertiesTest):

    @classmethod
    def setUpClass(cls):
        super(DomainCalculatedPropertiesTest, cls).setUpClass()
        cls.incoming_sms = cls.create_sms_in_es(cls.domain.name, INCOMING)

    @classmethod
    def tearDownClass(cls):
        cls.delete_sms_in_es(cls.incoming_sms)
        super(DomainCalculatedPropertiesTest, cls).tearDownClass()

    def test_calculated_properties_are_serializable(self):
        all_stats = all_domain_stats()
        props = calced_props(self.domain, self.domain._id, all_stats)
        json.dumps(props)

    def test_domain_does_not_have_apps(self):
        all_stats = all_domain_stats()
        props = calced_props(self.domain, self.domain._id, all_stats)
        self.assertFalse(props['cp_has_app'])


class GetSMSCountTest(BaseCalculatedPropertiesTest):

    def test_sms_count(self):
        sms_doc = self.create_sms_in_es(self.domain.name, INCOMING)
        self.addCleanup(self.delete_sms_in_es, sms_doc)
        self.assertEqual(SMSES().count(), 1)
        self.assertEqual(sms(self.domain.name, INCOMING), 1)
        self.assertEqual(sms(self.domain.name, OUTGOING), 0)

    def test_days_as_str_is_valid(self):
        sms_doc = self.create_sms_in_es(self.domain.name, INCOMING)
        self.addCleanup(self.delete_sms_in_es, sms_doc)
        count = get_sms_count(self.domain.name, days='30')
        self.assertEqual(count, 1)
