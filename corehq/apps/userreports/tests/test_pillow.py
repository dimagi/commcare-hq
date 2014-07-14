import json
import os
from django.test import TestCase
import sqlalchemy
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.pillow import ConfigurableIndicatorPillow
from corehq.apps.userreports.sql import rebuild_table
from corehq.apps.userreports.tests import get_sample_doc_and_indicators


class IndicatorPillowTest(TestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_config.json')
        with open(sample_file) as f:
            structure = json.loads(f.read())
            self.config = IndicatorConfiguration.wrap(structure)
            self.pillow = ConfigurableIndicatorPillow(self.config)

        # todo: figure out the right place for this to get called
        rebuild_table(self.pillow._table)
        self.engine = self.pillow.get_sql_engine()

    def tearDown(self):
        # todo: this is a little sketchy/coupled
        with self.engine.begin() as connection:
            self.pillow._table.drop(connection, checkfirst=True)
        self.pillow._engine.dispose()

    def testFilter(self):
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertFalse(self.pillow.python_filter(document))

        self.assertTrue(self.pillow.python_filter(dict(doc_type="CommCareCase", domain='user-reports', type='ticket')))

    def testChangeTransport(self):
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators()
        self.pillow.change_transport(sample_doc)
        with self.engine.begin() as connection:
            rows = connection.execute(sqlalchemy.select([self.pillow._table]))
            self.assertEqual(1, rows.rowcount)
            row = rows.fetchone()
            for k, v in row.items():
                self.assertEqual(expected_indicators[k], v)
