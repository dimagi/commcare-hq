import json
import os
from django.test import SimpleTestCase
from corehq.apps.userreports.models import IndicatorConfiguration


class IndicatorConfigurationTest(SimpleTestCase):


    def testLoadConfig(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_config.json')
        with open(sample_file) as f:
            structure = json.loads(f.read())
            config = IndicatorConfiguration.wrap(structure)
            self.assertEqual('user-reports', config.domain)
            self.assertEqual('sample', config.table_id)
            self.assertTrue(config.filter.filter(dict(doc_type="CommCareCase", domain='user-reports', type='ticket')))
            self.assertFalse(config.filter.filter(dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket')))
            self.assertFalse(config.filter.filter(dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket')))
            self.assertFalse(config.filter.filter(dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket')))

            # tbd, indicator checks
            indicators = config.indicators
