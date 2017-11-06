from __future__ import absolute_import
from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration
from custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases import \
    match_facility, ValidationFailure

TESTING_FACILITY_ID = 'testing_facility_id'
TESTING_FACILITY_NAME = 'testing_facility_name'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_pmdt_follow_up_test_name'


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        TESTING_FACILITY_ID,
        TESTING_FACILITY_NAME,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property(DATAMIGRATION_CASE_PROPERTY) != 'yes'
            and test.get_case_property('migration_type') == 'pmdt_excel'
            and test.get_case_property('rft_general') == 'follow_up_drtb'
        ):
            try:
                name, id = match_facility(domain, test.get_case_property(TESTING_FACILITY_NAME))
                return {
                    TESTING_FACILITY_NAME: name,
                    TESTING_FACILITY_ID: id
                }
            except ValidationFailure:
                return {}
        else:
            return {}
