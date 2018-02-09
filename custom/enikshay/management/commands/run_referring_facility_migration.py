from __future__ import absolute_import
from corehq.apps.locations.models import SQLLocation

from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
    get_form_path,
    get_test_created_form,
)

DATAMIGRATION_CASE_PROPERTY = 'datamigration_referring_facility'
REFERRING_FACILITY_ID = 'referring_facility_id'
REFERRING_FACILITY_SAVED_NAME = 'referring_facility_saved_name'


class Command(BaseEnikshayCaseMigration):
    case_type = 'test'
    case_properties_to_update = [
        REFERRING_FACILITY_ID,
        REFERRING_FACILITY_SAVED_NAME,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(test, domain):
        if (
            test.get_case_property(DATAMIGRATION_CASE_PROPERTY) == 'yes'
            or test.get_case_property(REFERRING_FACILITY_ID)
        ):
            return {}

        form_data_requesting_test = get_test_created_form(test)
        referring_facility_id = get_form_path(
            ['ql_referring_facility_details', 'referring_facility_id'],
            form_data_requesting_test
        )
        if not referring_facility_id:
            return {}

        update = {
            REFERRING_FACILITY_ID: referring_facility_id,
        }
        try:
            referring_facility_name = SQLLocation.objects.get(
                domain=domain,
                location_id=referring_facility_id,
            ).name
            update[REFERRING_FACILITY_SAVED_NAME] = referring_facility_name
        except SQLLocation.DoesNotExist:
            pass
        return update
