import csv
from datetime import datetime

from django.core.management import BaseCommand

from corehq.apps.es.cases import CaseES
from corehq.apps.hqcase.utils import (
    bulk_update_cases,
    get_last_non_blank_value,
)
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

CASE_UPDATE_BATCH = 100
DEVICE_ID = "reset_case_property"


class Command(BaseCommand):
    help = 'Reset a case name to last filled value if currently blank for open cases'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')

    def handle(self, domain, case_type, *args, **options):
        perform_update = True
        query = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .term('name.exact', '')
        )
        cases_count = query.count()
        print("Number of cases to be updated approximately: %s" % cases_count)
        if not input("Do you wish to update cases (y/n)") == 'y':
            perform_update = False
            if not input("Do you wish to just log updates (y/n)") == 'y':
                exit(0)
        case_ids = query.get_ids()
        print("Begin iterating %s cases" % len(case_ids))
        case_accessor = CaseAccessors(domain)
        case_updates = []
        filename = "case_updates_%s_%s_%s.csv" % (domain, case_type, datetime.utcnow())
        with open(filename, 'w') as f:
            writer = csv.DictWriter(f, ['case_id', 'new_value'])
            writer.writeheader()
            for case_id in with_progress_bar(case_ids):
                case = case_accessor.get_case(case_id)
                if case.name:
                    continue
                update_to_name = get_last_non_blank_value(case, 'name')
                if update_to_name:
                    writer.writerow({'case_id': case_id, 'new_value': update_to_name})
                    if perform_update:
                        case_updates.append((case_id, {'name': update_to_name}, False))
                # update batch when we have the threshold
                if len(case_updates) == CASE_UPDATE_BATCH:
                    bulk_update_cases(domain, case_updates, DEVICE_ID)
                    case_updates = []
            # submit left over case updates
            if case_updates:
                print("Performing last batch of updates")
                bulk_update_cases(domain, case_updates, DEVICE_ID)
            print("Finished. Update details in %s" % filename)
