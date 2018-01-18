import csv
from corehq.apps.locations.models import SQLLocation
from collections import defaultdict
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_person_case_from_episode
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock


locations_for_agency_id = defaultdict(list)
DOMAIN = "enikshay"
PARENT_CTD_LOCATION_ID = "fa7472fe0c9751e5d14595c1a092cd84"

for location in SQLLocation.active_objects.get_locations_and_children([PARENT_CTD_LOCATION_ID]):
    private_sector_agency_id = location.metadata.get('private_sector_agency_id')
    if private_sector_agency_id:
        locations_for_agency_id[private_sector_agency_id].append(location.location_id)


def find_location(agency_id):
    location_ids = locations_for_agency_id[agency_id]
    if len(location_ids) == 1:
        return location_ids[0]
    elif len(location_ids) > 1:
        print('multiple agency found %s' % agency_id)
    else:
        print('agency not found %s' % agency_id)
    return None


WRITE_FILE_HEADERS = [
    'Source_ID',
    'Current Treating Provider',
    'Current Treating Hospital',
    'Treating Provider Name',
    'Treating Provider Agency ID',
    'Treating Hospital Name',
    'Treating Hospital Agency ID',
    'all_good',
    'owner_id',
    'facility_assigned_to',
    'owner_and_facility_diff',
    'current_treating_provider',
    'current_treating_provider_diff',
    'expected_treating_provider',
    'expected_treating_provider_diff',
    'current_treating_hospital',
    'current_treating_hospital_diff',
    'expected_treating_hospital',
    'expected_treating_hospital_diff',
    'person_updates',
    'episode_updates'
]


def get_case_block(case_id, update_props, owner_id=None):
    if owner_id:
        return CaseBlock(
            case_id=case_id,
            owner_id=owner_id,
            update=update_props,
        )
    else:
        return CaseBlock(
            case_id=case_id,
            update=update_props,
        )


with open('mock_update_hospitals_and_providers_1596.csv', 'w') as output_file:
    writer = csv.DictWriter(output_file, fieldnames=WRITE_FILE_HEADERS)
    writer.writeheader()
    with open('update_hospitals_and_providers_1596.csv', 'rU') as input_file:
        case_accessor = CaseAccessors("enikshay")
        reader = csv.DictReader(input_file)
        for row in reader:
            all_good = True
            new_treating_provider_location_id = find_location(row['Treating Provider Agency ID'])
            new_treating_hospital_location_id = find_location(row['Treating Hospital Agency ID'])
            new_treating_provider = SQLLocation.active_objects.get_or_None(
                location_id=new_treating_provider_location_id)
            if not new_treating_provider:
                print('treating provider not found %s %s' % (row['Treating Provider Agency ID'], new_treating_provider_location_id))
                all_good = False
            new_treating_hospital = SQLLocation.active_objects.get_or_None(
                location_id=new_treating_hospital_location_id)
            if not new_treating_hospital:
                print('treating hospital not found %s %s' % (
                row['Treating Hospital Agency ID'], new_treating_hospital_location_id))
                all_good = False
            if new_treating_hospital and new_treating_provider:
                episode_case_id = row['Source_ID']
                episode_case = case_accessor.get_case(episode_case_id)
                person_case = get_person_case_from_episode(episode_case.domain, episode_case_id)
                expected_current_treating_provider_name = row['Current Treating Provider']
                expected_current_treating_hospital_name = row['Current Treating Hospital']
                current_treating_hospital_id = episode_case.get_case_property('episode_treating_hospital')
                current_treating_provider_id = person_case.owner_id

                row['owner_id'] = person_case.owner_id
                row['facility_assigned_to'] = person_case.get_case_property('facility_assigned_to')

                # check current provider id
                if person_case.owner_id != person_case.get_case_property('facility_assigned_to'):
                    print("%s person has diff owner and facility_assigned_to, %s" % (person_case.case_id, episode_case_id))
                    row['owner_and_facility_diff'] = True
                    all_good = False
                # check current provider name
                current_treating_provider = SQLLocation.active_objects.get_or_None(
                    location_id=current_treating_provider_id)
                row['current_treating_provider'] = current_treating_provider.name
                if current_treating_provider.name != expected_current_treating_provider_name:
                    print("%s has different treating provider than expected, %s" % (person_case.case_id, episode_case_id))
                    row['current_treating_provider_diff'] = True
                    all_good = False
                # check name of expected provider
                treating_provider_location_name = row['Treating Provider Name']
                treating_provider_location = SQLLocation.active_objects.get_or_None(
                    location_id=new_treating_provider_location_id)
                row['expected_treating_provider'] = treating_provider_location.name
                if treating_provider_location_name not in treating_provider_location.name:
                    print("%s has different treating provider name than expected, %s" % (person_case.case_id, episode_case_id))
                    row['expected_treating_provider_diff'] = True
                    all_good = False
                if current_treating_hospital_id:
                    current_treating_hospital = SQLLocation.active_objects.get_or_None(
                        location_id=current_treating_hospital_id)

                    # check current treating hospital name
                    row['current_treating_hospital'] = current_treating_hospital.name
                    if current_treating_hospital.name != expected_current_treating_hospital_name:
                        print("%s has different treating hospital than expected" % episode_case_id)
                        row['current_treating_hospital_diff'] = True
                    all_good = False
                # check name of expected hospital
                treating_hospital_location_name = row['Treating Hospital Name']
                treating_hospital_location = SQLLocation.active_objects.get_or_None(
                    location_id=new_treating_hospital_location_id)

                row['expected_treating_hospital'] = treating_hospital_location.name
                if treating_hospital_location_name not in treating_hospital_location.name:
                    print("%s has different treating hospital name than expected" % episode_case_id)
                    row['expected_treating_hospital_diff'] = True
                    all_good = False

                if all_good:
                    case_blocks = []
                    person_update_props = {}
                    if new_treating_provider_location_id != current_treating_provider_id:
                        person_update_props['facility_assigned_to'] = new_treating_provider_location_id
                        case_blocks.append(
                            get_case_block(
                                person_case.case_id,
                                person_update_props,
                                owner_id=new_treating_provider_location_id
                            )
                        )
                        row['person_updates'] = person_update_props

                    episode_update_props = {}
                    if new_treating_hospital_location_id != current_treating_hospital_id:
                        episode_update_props['episode_treating_hospital'] = new_treating_hospital_location_id
                        case_blocks.append(
                            get_case_block(
                                episode_case.case_id,
                                episode_update_props
                            )
                        )
                        row['episode_updates'] = episode_update_props

                    submit_case_blocks(
                        [case_block.as_string() for case_block in case_blocks],
                        DOMAIN,
                        device_id="reassign_enikshay_beneficiaries",
                    )
            else:
                if not new_treating_hospital:
                    print("Missing treating hospital for %s" % row['Treating Hospital Agency ID'])
                if not new_treating_provider:
                    print("Missing treating provider for %s" % row['Treating Hospital Agency ID'])

            row['all_good'] = all_good
            writer.writerow(row)
