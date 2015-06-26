import decimal
import uuid
from django.test import TestCase
from mock import patch
import sqlalchemy
from datetime import datetime
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
        self.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)

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

    @patch('corehq.apps.userreports.specs.datetime')
    def test_change_transport(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, _ = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.change_transport(sample_doc)
        self._check_sample_doc_state()

    @patch('corehq.apps.userreports.specs.datetime')
    def test_rebuild_indicators(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        self.config.save()
        sample_doc, _ = get_sample_doc_and_indicators(self.fake_time_now)
        CommCareCase.get_db().save_doc(sample_doc)
        rebuild_indicators(self.config._id)
        self._check_sample_doc_state()

    def test_bad_integer_datatype(self):
        self.config.save()
        bad_ints = ['a', '', None]
        for bad_value in bad_ints:
            self.pillow.change_transport({
                '_id': uuid.uuid4().hex,
                'doc_type': 'CommCareCase',
                'domain': 'user-reports',
                'type': 'ticket',
                'priority': bad_value
            })
        # make sure we saved rows to the table for everything
        with self.engine.begin() as connection:
            rows = connection.execute(sqlalchemy.select([self.adapter.get_table()]))
            self.assertEqual(len(bad_ints), rows.rowcount)

    @patch('corehq.apps.userreports.specs.datetime')
    def _check_sample_doc_state(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        _, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        with self.engine.begin() as connection:
            rows = connection.execute(sqlalchemy.select([self.adapter.get_table()]))
            self.assertEqual(1, rows.rowcount)
            row = rows.fetchone()
            for k, v in row.items():
                if isinstance(expected_indicators[k], decimal.Decimal):
                    self.assertAlmostEqual(expected_indicators[k], v)
                else:
                    self.assertEqual(expected_indicators[k], v)
