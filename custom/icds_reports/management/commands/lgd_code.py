import csv
import json
from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
headers = [
    'location_Id',
    'lgd_code'
]
data_rows = [headers]


class Command(BaseCommand):
    help = "Fetch lgd codes"

    def handle(self, **options):
        locations = SQLLocation.objects.filter(location_type__name='awc').values('location_id','metadata')
        data_rows = [headers]
        count = 0
        for location in locations:
            count = count + 1
            if count % 1000 == 0:
                print(f"processed entries {count}\n")
            lgd_code = ''
            metadata = json.loads(location['metadata'])
            if "lgd_code" in metadata:
                lgd_code = metadata['lgd_code']
            row = [
                location['location_id'],
                lgd_code
            ]
            data_rows.append(row)

        fout = open('/home/cchq/lgd_codes_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(data_rows)

