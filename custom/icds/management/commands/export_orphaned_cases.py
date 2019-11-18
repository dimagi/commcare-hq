import csv

from django.core.management import BaseCommand

from corehq.apps.es import CaseES, filters
from corehq.apps.locations.models import SQLLocation

from dimagi.utils.chunked import chunked

from corehq.util.log import with_progress_bar

CHILD_PROPERTIES = ['case_id', 'owner_id', 'opened_on', 'modified_on',
                    'name', 'aadhar_number', 'dob', 'died']

SOURCE_FIELDS = CHILD_PROPERTIES + ['indices']

CSV_HEADERS = CHILD_PROPERTIES + ['owner_name', 'hh_id', 'hh_name', 'hh_closed_on']


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'child_file',
            help="File path child case output file",
        )

    def handle(self, child_file, **options):
        relevant_districts = SQLLocation.objects.filter(domain='icds-cas',
                                                        location_id__in=['d982a6fb4cca0824fbde59db18d2d422',
                                                                         '0ffe4a1f110ffc17bb9b749abdfd697c'])
        owners = SQLLocation.objects.get_queryset_descendants(relevant_districts, include_self=True)
        owner_name_mapping = {loc.location_id: loc.name for loc in owners}
        hh_cases = self._get_closed_hh_cases(list(owner_name_mapping))
        with open(child_file, 'w', encoding='utf-8') as child_csv:
            child_writer = csv.writer(child_csv)
            child_writer.writerow(CSV_HEADERS)
            for cases in chunked(with_progress_bar(hh_cases, hh_cases.count), 500):
                household_ids = []
                hh_map = {}
                for hh in cases:
                    hh_map[hh['case_id']] = (hh['name'].encode('utf-8'), hh.get('closed_on', '').encode('utf-8'))
                    household_ids.append(hh['case_id'])
                child_cases = self._get_child_cases(household_ids)
                ids = set(household_ids)
                for child in child_cases.hits:
                    parent_index = filter(
                        lambda index: index['referenced_id'] in ids and index['identifier'] == 'parent',
                        child['indices']
                    )[0]
                    if parent_index:
                        hh_id = parent_index['referenced_id']
                        row = [child.get(prop, '').encode('utf-8') for prop in CHILD_PROPERTIES]
                        row.append(owner_name_mapping.get(child.get('owner_id', ''), '').encode('utf-8'))
                        hh_info = (hh_id, hh_map[hh_id][0], hh_map[hh_id][1])
                        row.extend(hh_info)
                        child_writer.writerow(row)

    def _get_closed_hh_cases(self, owners):
        query = (CaseES(es_instance_alias='export')
                 .is_closed()
                 .domain('icds-cas')
                 .case_type('household')
                 .owner(owners)
                 .source(['case_id', 'closed_on', 'name'])
                 .size(100)
                 )
        return query.scroll()

    def _get_child_cases(self, household_ids):
        query = (CaseES(es_instance_alias='export')
                 .domain('icds-cas')
                 .case_type('person')
                 .is_closed(False)
                 .source(SOURCE_FIELDS)
                 .filter(filters.term("indices.referenced_id", household_ids))
                )
        return query.run()
