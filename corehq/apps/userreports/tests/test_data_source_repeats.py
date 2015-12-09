import json
import os
import datetime
from django.test import SimpleTestCase, TestCase
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter


DOC_ID = 'repeat-id'
DAY_OF_WEEK = 'monday'


class RepeatDataSourceTestMixin(object):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'data_source_with_repeat.json')
        with open(sample_file) as f:
            self.config = DataSourceConfiguration.wrap(json.loads(f.read()))


class RepeatDataSourceConfigurationTest(RepeatDataSourceTestMixin, SimpleTestCase):

    def test_test_doc_matches(self):
        self.assertTrue(self.config.filter(_test_doc()))

    def test_empty_doc_no_rows(self):
        self.assertEqual([], self.config.get_all_values(_test_doc()))

    def test_missing_property_no_rows(self):
        self.assertEqual([], self.config.get_all_values(_test_doc(form={})))

    def test_null_property_no_rows(self):
        self.assertEqual([], self.config.get_all_values(_test_doc(form={"time_logs": None})))

    def test_empty_list_property_no_rows(self):
        self.assertEqual([], self.config.get_all_values(_test_doc(form={"time_logs": []})))

    def test_dict_property(self):
        start = datetime.datetime.utcnow()
        end = start + datetime.timedelta(minutes=30)
        rows = self.config.get_all_values(_test_doc(form={"time_logs": {
            "start_time": start, "end_time": end, "person": "al"
        }}))
        self.assertEqual(1, len(rows))
        doc_id_ind, inserted_at, repeat_iteration, start_ind, end_ind, person_ind, created_base_ind = rows[0]
        self.assertEqual(DOC_ID, doc_id_ind.value)
        self.assertEqual(0, repeat_iteration.value)
        self.assertEqual(start, start_ind.value)
        self.assertEqual(end, end_ind.value)
        self.assertEqual('al', person_ind.value)
        self.assertEqual(DAY_OF_WEEK, created_base_ind.value)

    def test_list_property(self):
        now = datetime.datetime.utcnow()
        one_hour = datetime.timedelta(hours=1)
        logs = [
            {"start_time": now, "end_time": now + one_hour, "person": "al"},
            {"start_time": now + one_hour, "end_time": now + (one_hour * 2), "person": "chris"},
            {"start_time": now + (one_hour * 2), "end_time": now + (one_hour * 3), "person": "katie"},
        ]
        rows = self.config.get_all_values(_test_doc(form={"time_logs": logs}))
        self.assertEqual(len(logs), len(rows))
        for i, row in enumerate(rows):
            doc_id_ind, inserted_at, repeat_iteration, start_ind, end_ind, person_ind, created_base_ind = row
            self.assertEqual(DOC_ID, doc_id_ind.value)
            self.assertEqual(logs[i]['start_time'], start_ind.value)
            self.assertEqual(i, repeat_iteration.value)
            self.assertEqual(logs[i]['end_time'], end_ind.value)
            self.assertEqual(logs[i]['person'], person_ind.value)
            self.assertEqual(DAY_OF_WEEK, created_base_ind.value)


class RepeatDataSourceBuildTest(RepeatDataSourceTestMixin, TestCase):

    def test_table_population(self):

        adapter = IndicatorSqlAdapter(self.config)
        # Delete and create table
        adapter.rebuild_table()

        # Create a doc
        now = datetime.datetime.now()
        one_hour = datetime.timedelta(hours=1)
        logs = [
            {"start_time": now, "end_time": now + one_hour, "person": "al"},
            {"start_time": now + one_hour, "end_time": now + (one_hour * 2), "person": "chris"},
            {"start_time": now + (one_hour * 2), "end_time": now + (one_hour * 3), "person": "katie"},
        ]
        doc = _test_doc(form={'time_logs': logs})

        # Save this document into the table
        adapter.save(doc)

        # Get rows from the table
        rows = adapter.get_query_object()
        retrieved_logs = [
            {
                'start_time': r.start_time,
                'end_time': r.end_time,
                'person': r.person,

            } for r in rows
        ]
        # Check those rows against the expected result
        self.assertItemsEqual(
            retrieved_logs,
            logs,
            "The repeat data saved in the data source table did not match the expected data!"
        )


def _test_doc(**extras):
    test_doc = {
        "_id": DOC_ID,
        "domain": "user-reports",
        "doc_type": "XFormInstance",
        "created": DAY_OF_WEEK
    }
    test_doc.update(extras)
    return test_doc
