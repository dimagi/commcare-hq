import sys
from typing import Iterator, List

from django.core.management import BaseCommand

from custom.onse.models import CasePropertyMap, iter_mappings, write_mappings
from custom.onse.tasks import get_dhis2_server


class Command(BaseCommand):
    help = ('Fetch data set IDs from DHIS2 and update a CSV file of '
            'mappings from case property names to DHIS2 data element '
            'IDs and the IDs of the data sets they belong to.')

    def handle(self, *args, **options):
        # Read all mappings to close the CSV file, because
        # `write_mappings()` will be writing to the same file.
        mappings = list(iter_mappings())
        mappings = set_data_set_ids(mappings)
        write_mappings(mappings)


def set_data_set_ids(
    mappings: List[CasePropertyMap],
) -> Iterator[CasePropertyMap]:
    dhis2_server = get_dhis2_server()
    requests = dhis2_server.get_requests()
    for mapping in mappings:
        endpoint = f'/api/dataElements/{mapping.data_element_id}.json'
        response = requests.get(endpoint)
        if response.status_code == 404:
            print(f'{mapping.dhis2_name} ({mapping.data_element_id}) not '
                  'found. It will be excluded from the mappings file.',
                  file=sys.stderr)
            continue
        mapping.data_set_id = response.json()['dataSetElements'][0]['dataSet']['id']
        yield mapping
