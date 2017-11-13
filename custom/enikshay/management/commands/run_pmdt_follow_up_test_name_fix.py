from __future__ import absolute_import
from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration
from custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases import \
    match_facility, ValidationFailure

TESTING_FACILITY_ID = 'testing_facility_id'
TESTING_FACILITY_NAME = 'testing_facility_name'
RFT_GENERAL = 'rft_general'
MIGRATION_TYPE = 'migration_type'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_pmdt_follow_up_test_name'


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    # Not all these case properties are updated but want their output for debugging
    case_properties_to_update = [
        TESTING_FACILITY_ID,
        TESTING_FACILITY_NAME,
        RFT_GENERAL,
        MIGRATION_TYPE,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property(DATAMIGRATION_CASE_PROPERTY) != 'yes'
            and test.get_case_property(MIGRATION_TYPE) == 'pmdt_excel'
            and test.get_case_property(RFT_GENERAL) == 'follow_up_drtb'
            and test.get_case_property(TESTING_FACILITY_NAME)
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
