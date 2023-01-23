import datetime
import json

from django.test import TestCase

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.domain.calculations import (
    all_domain_stats,
    calced_props,
    get_sms_count,
    sms,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.sms import SMSES, sms_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.sms.models import INCOMING, OUTGOING


@es_test(requires=[case_adapter, form_adapter, sms_adapter, user_adapter])
class BaseCalculatedPropertiesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseCalculatedPropertiesTest, cls).setUpClass()
        cls.domain = Domain(name='test-b9289e19d819')
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)

    def setUp(self):
        super().setUp()
        sms_doc = {
            '_id': 'some_sms_id',
            'domain': self.domain.name,
            'direction': INCOMING,
            'date': json_format_datetime(datetime.datetime.utcnow()),
        }
        sms_adapter.index(sms_doc, refresh=True)


class DomainCalculatedPropertiesTest(BaseCalculatedPropertiesTest):

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
        self.assertEqual(SMSES().count(), 1)
        self.assertEqual(sms(self.domain.name, INCOMING), 1)
        self.assertEqual(sms(self.domain.name, OUTGOING), 0)

    def test_days_as_str_is_valid(self):
        count = get_sms_count(self.domain.name, days='30')
        self.assertEqual(count, 1)
