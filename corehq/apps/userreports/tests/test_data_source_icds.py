import json
import os
from datetime import date
from django.test import SimpleTestCase
from corehq.apps.userreports.models import DataSourceConfiguration


class ICDSDataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'icds_poc.json')
        with open(sample_file) as f:
            self.config = DataSourceConfiguration.wrap(json.loads(f.read()))

    def test_items(self):
        doc = {
            "domain": "icds-test",
            "doc_type": "XFormInstance",
            "received_on": date(2016, 1, 29),
            "case_opened_on": date(2015, 11, 15),
            "case_closed_on": date(2016, 2, 15),
        }

        for row in self.config.get_all_values(doc):
            print row

