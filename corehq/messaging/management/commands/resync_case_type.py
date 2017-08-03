from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.util.log import with_progress_bar
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sync messaging models for cases"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('--limit', type=int, default=-1)

    def handle(self, domain, case_type, limit, **options):
        print("Fetching case ids for %s/%s ..." % (domain, case_type))
        case_ids = CaseAccessors(domain).get_case_ids_in_domain(case_type)

        print("Creating tasks...")
        if limit > 0:
            case_ids = case_ids[:limit]
            print("Limiting to %s tasks..." % limit)

        for case_id in with_progress_bar(case_ids):
            sync_case_for_messaging.delay(domain, case_id)
