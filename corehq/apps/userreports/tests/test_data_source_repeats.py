import json
import os
import datetime
from django.test import SimpleTestCase
from corehq.apps.userreports.models import DataSourceConfiguration


class RepeatDataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'data_source_with_repeat.json')
        with open(sample_file) as f:
            self.config = DataSourceConfiguration.wrap(json.loads(f.read()))

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
        start = datetime.datetime.now()
        end = start + datetime.timedelta(minutes=30)
        rows = self.config.get_all_values(_test_doc(form={"time_logs": {
            "start_time": start, "end_time": end, "person": "al"
        }}))
        self.assertEqual(1, len(rows))
        doc_id_ind, start_ind, end_ind, person_ind = rows[0]
        self.assertEqual(start, start_ind.value)
        self.assertEqual(end, end_ind.value)
        self.assertEqual('al', person_ind.value)

    def test_list_property(self):
        now = datetime.datetime.now()
        one_hour = datetime.timedelta(hours=1)
        logs = [
            {"start_time": now, "end_time": now + one_hour, "person": "al"},
            {"start_time": now + one_hour, "end_time": now + (one_hour * 2), "person": "chris"},
            {"start_time": now + (one_hour * 2), "end_time": now + (one_hour * 3), "person": "katie"},
        ]
        rows = self.config.get_all_values(_test_doc(form={"time_logs": logs}))
        self.assertEqual(len(logs), len(rows))
        for i, row in enumerate(rows):
            doc_id_ind, start_ind, end_ind, person_ind = row
            self.assertEqual(logs[i]['start_time'], start_ind.value)
            self.assertEqual(logs[i]['end_time'], end_ind.value)
            self.assertEqual(logs[i]['person'], person_ind.value)


TODO = {
    "type": "expression",
    "expression": {
        "type": "base_doc_expression",
        "expression": {
            "type": "property_name",
            "property_name": "created"
        }
    },
    "column_id": "start_time",
    "datatype": "datetime",
    "display_name": "start time"
}

def _test_doc(**extras):
    test_doc = {
        "domain": "user-reports",
        "doc_type": "XFormInstance"
    }
    test_doc.update(extras)
    return test_doc
