from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestMigrationForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-migration_form"

    def test_migration_form(self):
        self._test_data_source_results(
            'migration_form_v31895',
            [{
                "doc_id": None,
                "timeend": None,
                "migration_status": 'migrated',
                "person_case_id": "b08669b9-f8d5-4dfb-891f-8727a4486682"
            }])
