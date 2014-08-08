import json
import os
from django.test import TestCase
import sqlalchemy
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.pillow import ConfigurableIndicatorPillow
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.tests import get_sample_doc_and_indicators


class IndicatorPillowTest(TestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_indicator_config.json')
        self.pillow = ConfigurableIndicatorPillow()
        self.engine = self.pillow.get_sql_engine()
        with open(sample_file) as f:
            structure = json.loads(f.read())
            self.config = IndicatorConfiguration.wrap(structure)
            self.pillow.bootstrap(configs=[self.config])

        self.adapter = IndicatorSqlAdapter(self.engine, self.config)
        self.adapter.rebuild_table()

    def tearDown(self):
        self.adapter.drop_table()
        self.engine.dispose()

    def testFilter(self):
        # note: this is a silly test now that python_filter always returns true
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertTrue(self.pillow.python_filter(document))

        self.assertTrue(self.pillow.python_filter(dict(doc_type="CommCareCase", domain='user-reports', type='ticket')))

    def testChangeTransport(self):
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators()
        self.pillow.change_transport(sample_doc)
        with self.engine.begin() as connection:
            rows = connection.execute(sqlalchemy.select([self.adapter.get_table()]))
            self.assertEqual(1, rows.rowcount)
            row = rows.fetchone()
            for k, v in row.items():
                self.assertEqual(expected_indicators[k], v)
