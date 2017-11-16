from __future__ import print_function
import csv
from collections import namedtuple, defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation

domain = "enikshay"

LocationDetail = namedtuple('LocationDetail', 'name nikshay_code nikshay_code_2 mobile loc_type nikshay_tu_id')
nikshay_locations = {}
enikshay_locations = {}
nikshay_codes_in_multiple_locations = defaultdict(set)


class Command(BaseCommand):
    """
    Takes a list of nikshay locations with its nikshay code and then finds corresponding
    locations in eNikshay using that Nikshay Code.
    Headers for input file:
    Name, Nikshay Code, Mobile, Type, Nikshay Code 2, Nikshay TU ID
    where Nikshay Code and Nikshay Code 2 are usually similar with padding like
    123 and 0123 so safe to check for both when searching in eNikshay
    Then generates a report to show
    1. Duplicates in eNikshay where more than one location has the same nikshay code
    2. matches along with Nikshay TU ID for locations for comparison
    3. nikshay codes that were not found in eNikshay
    Generates two reports
    1. The comparison report for all nikshay codes received
    2. Location ids in case of duplicates for a nikshay codes
    """
    def add_arguments(self, parser):
        parser.add_argument('file_path')

    def handle(self, file_path, *args, **options):
        # Iterate the input file and create a dict with each nikshay code as key and the
        # corresponding details as value
        # While iterating in case of duplicates Take the latest value
        with open(file_path, 'rU') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Nikshay Code'] in nikshay_locations:
                    print("Found two rows for nikshay code {code}. Taking latest."
                          .format(code=row['Nikshay Code']))
                nikshay_locations[row['Nikshay Code'].strip()] = LocationDetail(
                    name=row['Name'],
                    nikshay_code=row['Nikshay Code'].strip(),
                    nikshay_code_2=row['Nikshay Code 2'].strip(),
                    mobile=row['Mobile'],
                    loc_type=row['Type'],
                    nikshay_tu_id=row['Nikshay TU ID']
                )
                # also track Nikshay Code 2 if its separate from Nikshay Code
                if row['Nikshay Code'].strip() != row['Nikshay Code 2'].strip():
                    nikshay_locations[row['Nikshay Code 2'].strip()] = LocationDetail(
                        name=row['Name'],
                        nikshay_code=row['Nikshay Code'].strip(),
                        nikshay_code_2=row['Nikshay Code 2'].strip(),
                        mobile=row['Mobile'],
                        loc_type=row['Type'],
                        nikshay_tu_id=row['Nikshay TU ID']
                    )
        # Iterate over locations ignoring test locations and create a dict with nikshay code
        # as key and location object as value.
        # While iterating keep track of duplicates and store them separately for report later
        for location in SQLLocation.active_objects.filter(domain=domain):
            loc_metadata = location.metadata
            is_test = (loc_metadata.get('is_test', 'yes') == 'yes')
            if not is_test:
                location_nikshay_code = loc_metadata.get('nikshay_code', '').strip()
                if location_nikshay_code:
                    if location_nikshay_code in enikshay_locations:
                        nikshay_codes_in_multiple_locations[location_nikshay_code].add(
                            enikshay_locations[location_nikshay_code].location_id
                        )
                        nikshay_codes_in_multiple_locations[location_nikshay_code].add(
                            location.location_id
                        )
                    enikshay_locations[location_nikshay_code] = location

        result_file = "locations_codes_match_result_{timestamp}.csv".format(
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        headers = ['name', 'nikshay_code', 'nikshay_code_2',
                   'mobile', 'type', 'nikshay_tu_id',
                   'enikshay_name', 'enikshay_nikshay_code', 'enikshay_nikshay_tu_id',
                   'is_test', 'location_id', 'duplicates'
                   ]

        with open(result_file, 'w') as output_buffer:
            writer = csv.DictWriter(output_buffer, fieldnames=headers)
            writer.writeheader()
            # Iterate over all nikshay codes and find corresponding enikshay location
            # and then add report for the match accordingly
            for nikshay_code, nikshay_location_detail in nikshay_locations.items():
                enikshay_location = enikshay_locations.get(nikshay_location_detail.nikshay_code)
                row = {
                    'name': nikshay_location_detail.name,
                    'nikshay_code': nikshay_location_detail.nikshay_code,
                    'nikshay_code_2': nikshay_location_detail.nikshay_code_2,
                    'mobile': nikshay_location_detail.mobile,
                    'type': nikshay_location_detail.loc_type,
                    'nikshay_tu_id': nikshay_location_detail.nikshay_tu_id,
                    'duplicates': ','.join(
                        nikshay_codes_in_multiple_locations.get(
                            nikshay_location_detail.nikshay_code, []
                        ))
                }
                if enikshay_location:
                    loc_metadata = enikshay_location.metadata
                    row['enikshay_name'] = enikshay_location.name
                    row['enikshay_nikshay_code'] = loc_metadata.get('nikshay_code')
                    row['enikshay_nikshay_tu_id'] = loc_metadata.get('nikshay_tu_id')
                    row['is_test'] = loc_metadata.get('is_test')
                    row['location_id'] = enikshay_location.location_id
                writer.writerow(row)

        duplicate_locs_file = "locations_codes_duplicate_{timestamp}.csv".format(
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )

        # add reports for all duplicates found in enikshay for nikshay codes
        # present in the input file
        with open(duplicate_locs_file, 'w') as output_buffer:
            headers = ['nikshay_code', 'location_ids']
            writer = csv.DictWriter(output_buffer, fieldnames=headers)
            writer.writeheader()
            for nikshay_code in nikshay_codes_in_multiple_locations:
                writer.writerow({
                    'nikshay_code': nikshay_code,
                    'location_ids': ','.join(nikshay_codes_in_multiple_locations[nikshay_code])
                })
