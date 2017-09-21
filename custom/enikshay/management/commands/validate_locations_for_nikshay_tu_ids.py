from django.core.management.base import BaseCommand

import csv
from datetime import datetime
from corehq.apps.locations.models import SQLLocation
from collections import namedtuple
from collections import defaultdict

MockLocation = namedtuple('MockLocation', 'location_id nikshay_tu_id')

CTD_LOCATION_ID = "fa7472fe0c9751e5d14595c1a092cd84"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file_path')

    def handle(self, file_path, *args, **options):
        result_file = "location_tu_ids_validation_{ts}.csv".format(ts=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
        ctd_locations = SQLLocation.active_objects.get_locations_and_children([CTD_LOCATION_ID])
        nikshay_tu_ids = {}
        nikshay_tu_ids = defaultdict(lambda: [], nikshay_tu_ids)
        for location in ctd_locations:
            if location.metadata.get('nikshay_code'):
                nikshay_tu_ids[location.metadata.get('nikshay_code')].append(MockLocation(
                    location_id=location.location_id,
                    nikshay_tu_id=location.metadata.get('nikshay_tu_id')
                ))
        nikshay_locations = {}
        with open(file_path, 'rU') as read_buffer:
            reader = csv.DictReader(read_buffer)
            for row in reader:
                nikshay_locations[row['id']] = row['tu_id']
        with open(result_file, 'w') as output_buffer:
            writer = csv.writer(output_buffer)
            for nikshay_location_id in nikshay_locations:
                enikshay_tu_ids = nikshay_tu_ids[nikshay_location_id]
                for enikshay_tu_id in enikshay_tu_ids:
                    writer.writerow([
                        enikshay_tu_id.location_id,
                        nikshay_location_id, enikshay_tu_id.nikshay_tu_id, nikshay_locations[nikshay_location_id],
                        enikshay_tu_id.nikshay_tu_id == nikshay_locations[nikshay_location_id]
                    ])
