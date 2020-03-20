import datetime

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestMigrationForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-migration_form"

    def test_migration_form_without_date_left(self):
        self._test_data_source_results(
            'migration_form_v31895',
            [{
                "date_left": None,
                "doc_id": None,
                "timeend": datetime.datetime(2019, 12, 9, 8, 19, 4, 820000),
                "is_migrated": 1,
                "person_case_id": "b08669b9-f8d5-4dfb-891f-8727a4486682"
            }])

    def test_migration_form_with_date_left(self):
        self._test_data_source_results(
            'migration_form_v32203',
            [{
                "date_left": datetime.datetime(2020, 1, 29, 0, 0),
                "doc_id": None,
                "timeend": datetime.datetime(2020, 1, 29, 7, 37, 50, 957000),
                "is_migrated": 1,
                "person_case_id": "0b402471-c2e7-4cc5-b8c8-8cb0c4cdc4b1"
            }])
