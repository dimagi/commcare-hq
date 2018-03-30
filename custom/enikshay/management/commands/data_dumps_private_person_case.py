from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

from corehq.apps.locations.models import SQLLocation

from custom.enikshay.case_utils import (
    CASE_TYPE_PERSON,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import (
    BaseDataDump,
    PRIVATE_SECTOR_ID_MAPPING,
)
DOMAIN = "enikshay"


class Command(BaseDataDump):
    """ data dumps for private person cases

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1299017227&range=A41
    """
    TASK_NAME = "01_private_person_case"
    INPUT_FILE_NAME = "data_dumps_private_person_case.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_PERSON

    def get_custom_value(self, column_name, case):
        if column_name == "Organisation":
            owner_id = case.owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                private_sector_org_id = location.metadata.get('private_sector_org_id')
                if private_sector_org_id:
                    return PRIVATE_SECTOR_ID_MAPPING.get(private_sector_org_id, private_sector_org_id)
                else:
                    raise Exception("Private Sector Organization ID not set for location %s" % owner_id)
            else:
                raise Exception("Location not found for id %s" % owner_id)
        elif column_name == "Facility/Provider assigned to Name - ID":
            owner_id = case.owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                return location.name
            else:
                return "Location not found with id: %s" % owner_id
        elif column_name == "Facility/Provider assigned to type":
            owner_id = case.owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                return location.location_type.name
            else:
                return "Location not found with id: %s" % owner_id
        elif column_name == "Treating hospital Name":
            treating_hospital_id = case.get_case_property('treating_hospital')
            if treating_hospital_id:
                location = SQLLocation.active_objects.get_or_None(location_id=treating_hospital_id)
                if location:
                    return location.name
                else:
                    return "Treating hospital Location not found with id: %s" % treating_hospital_id
            else:
                return "Treating hospital id not found on case"
        elif column_name == "Associated FO Name":
            fo_id = case.get_case_property('fo')
            if fo_id:
                try:
                    return SQLLocation.objects.get(location_id=fo_id).name
                except SQLLocation.DoesNotExist:
                    return "FO Location not found with id: %s" % fo_id
            else:
                return "FO id not found on case"
        elif column_name == "State/Union territory":
            current_address_state_choice = case.get_case_property('current_address_state_choice')
            if current_address_state_choice:
                try:
                    return SQLLocation.objects.get(location_id=current_address_state_choice).name
                except SQLLocation.DoesNotExist:
                    return "Location not found with id: %s" % current_address_state_choice
        elif column_name == "District":
            current_address_district_choice = case.get_case_property('current_address_district_choice')
            if current_address_district_choice:
                try:
                    return SQLLocation.objects.get(location_id=current_address_district_choice).name
                except SQLLocation.DoesNotExist:
                    return "Location not found with id: %s" % current_address_district_choice
        elif column_name == "Block":
            current_address_block_taluka_mandal = case.get_case_property('current_address_block_taluka_mandal')
            if current_address_block_taluka_mandal:
                try:
                    return SQLLocation.objects.get(location_id=current_address_block_taluka_mandal).name
                except SQLLocation.DoesNotExist:
                    return "Location not found with id: %s" % current_address_block_taluka_mandal
        elif column_name == "Ward":
            current_address_ward = case.get_case_property('current_address_ward')
            if current_address_ward:
                try:
                    return SQLLocation.objects.get(location_id=current_address_ward).name
                except SQLLocation.DoesNotExist:
                    return "Location not found with id: %s" % current_address_ward
        raise Exception("unknown custom column %s" % column_name)

    def get_case_ids_query(self, case_type):
        """
        All open and closed person cases with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true')
                .case_property_query("dataset", 'real')
                )

    def include_case_in_dump(self, case):
        return self.person_belongs_to_real_location(case)
