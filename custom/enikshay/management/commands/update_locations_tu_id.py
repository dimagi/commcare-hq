from __future__ import absolute_import
import csv

from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation

domain = "enikshay"
enikshay_locations = defaultdict(list)


class Command(BaseCommand):
    """
    Receive a file with mapping between agency ids and resepective Nikshay TU ID
    Find enikshay locations using agency id and update them with the Nikshay TU ID
    where needed
    Headers for input file:
    Treating Provider, Agency ID, Nikshay Code, Nikshay TU ID
    Generates a report for updates highlighting both old and new enikshay ID
    """
    def add_arguments(self, parser):
        parser.add_argument('file_path')
        parser.add_argument('--dry_run', action='store_true')

    def handle(self, file_path, *args, **options):
        dry_run = options.get('dry_run')

        for location in SQLLocation.active_objects.filter(domain=domain):
            loc_metadata = location.metadata
            loc_agency_id = loc_metadata.get('private_sector_agency_id', '').strip()
            if loc_agency_id:
                enikshay_locations[loc_agency_id].append(location)

        result_file = "locations_codes_update_result_{timestamp}.csv".format(
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        with open(file_path, 'rU') as input_buffer:
            reader = csv.DictReader(input_buffer)
            with open(result_file, 'w') as output_buffer:
                writer = csv.DictWriter(output_buffer, fieldnames=[
                    'Treating Provider', 'Agency ID', 'Nikshay Code', 'Nikshay TU ID',
                    'eNikshay Name', 'eNikshay Nikshay Code', 'eNikshay Nikshay TU ID',
                    'eNikshay Location ID', 'new eNikshay Nikshay TU ID'
                ])
                writer.writeheader()
                for row in reader:
                    agency_id = row['Agency ID'].strip()
                    nikshay_provider = row['Treating Provider']
                    nikshay_code = row['Nikshay Code'].strip()
                    nikshay_tu_id = row['Nikshay TU ID'].strip()
                    if agency_id in enikshay_locations:
                        for enikshay_location in enikshay_locations[agency_id]:
                            loc_metadata = enikshay_location.metadata
                            enikshay_tu_id = enikshay_location.metadata['nikshay_tu_id']
                            new_enikshay_tu_id = "Not Updated"
                            if not dry_run:
                                if enikshay_tu_id != nikshay_tu_id:
                                    enikshay_location.metadata['nikshay_tu_id'] = nikshay_tu_id
                                    enikshay_location.save()
                                    new_enikshay_tu_id = nikshay_tu_id

                            writer.writerow({
                                'Agency ID': agency_id,
                                'Treating Provider': nikshay_provider,
                                'Nikshay Code': nikshay_code,
                                'Nikshay TU ID': nikshay_tu_id,
                                'eNikshay Name': enikshay_location.name,
                                'eNikshay Nikshay Code': loc_metadata.get('nikshay_code'),
                                'eNikshay Nikshay TU ID': enikshay_tu_id,
                                'eNikshay Location ID': enikshay_location.location_id,
                                'new eNikshay Nikshay TU ID': new_enikshay_tu_id
                            })
                    else:
                        writer.writerow({
                            'Agency ID': agency_id,
                            'Treating Provider': nikshay_provider,
                            'Nikshay Code': nikshay_code,
                            'Nikshay TU ID': nikshay_tu_id,
                        })
