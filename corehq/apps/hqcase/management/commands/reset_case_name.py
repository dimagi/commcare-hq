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
        query = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .term('name.exact', '')
        )
        cases_count = query.count()
        print("Number of cases to be updated approximately: %s" % cases_count)
        if not input("Do you wish to proceed (y/n)") == 'y':
            print("Aborting")
            return
        case_ids = query.get_ids()
        print("Being update for %s cases" % len(case_ids))
        case_accessor = CaseAccessors(domain)
        case_updates = []
        for case_id in with_progress_bar(case_ids):
            case = case_accessor.get_case(case_id)
            if case.name:
                continue
            update_to_name = get_last_non_blank_value(case, 'name')
            if update_to_name:
                case_updates.append((case_id, {'name': update_to_name}, False))
            # update batch when we have the threshold
            if len(case_updates) == CASE_UPDATE_BATCH:
                bulk_update_cases(domain, case_updates, DEVICE_ID)
                case_updates = []
        print("Performing last batch of updates")
        # submit left over case updates
        if case_updates:
            bulk_update_cases(domain, case_updates, DEVICE_ID)
        print("Updates finished.")
