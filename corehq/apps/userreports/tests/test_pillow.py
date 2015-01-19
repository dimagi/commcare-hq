from django.test import TestCase
import sqlalchemy
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.pillow import ConfigurableIndicatorPillow
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests import get_sample_doc_and_indicators, get_sample_data_source


class IndicatorPillowTest(TestCase):

    def setUp(self):
        self.config = get_sample_data_source()
        self.pillow = ConfigurableIndicatorPillow()
        self.engine = self.pillow.get_sql_engine()
        self.pillow.bootstrap(configs=[self.config])
        self.adapter = IndicatorSqlAdapter(self.engine, self.config)
        self.adapter.rebuild_table()

    def tearDown(self):
        self.adapter.drop_table()
        self.engine.dispose()

    def test_filter(self):
        # note: this is a silly test now that python_filter always returns true
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertTrue(self.pillow.python_filter(document))

        self.assertTrue(self.pillow.python_filter(
            dict(doc_type="CommCareCase", domain='user-reports', type='ticket')
        ))

    def test_change_transport(self):
        sample_doc, _ = get_sample_doc_and_indicators()
        self.pillow.change_transport(sample_doc)
        self._check_sample_doc_state()

    def test_rebuild_indicators(self):
        self.config.save()
        sample_doc, _ = get_sample_doc_and_indicators()
        CommCareCase.get_db().save_doc(sample_doc)
        rebuild_indicators(self.config._id)
        self._check_sample_doc_state()

    def _check_sample_doc_state(self):
        _, expected_indicators = get_sample_doc_and_indicators()
        with self.engine.begin() as connection:
            rows = connection.execute(sqlalchemy.select([self.adapter.get_table()]))
            self.assertEqual(1, rows.rowcount)
            row = rows.fetchone()
            for k, v in row.items():
                if isinstance(expected_indicators[k], decimal.Decimal):
                    self.assertAlmostEqual(expected_indicators[k], v)
                else:
                    self.assertEqual(expected_indicators[k], v)
