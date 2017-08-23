from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.util.log import with_progress_bar
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync messaging models for cases"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')

    def handle(self, domain, case_type, **options):
        print("Fetching case ids for %s/%s ..." % (domain, case_type))
        case_ids = CaseAccessors(domain).get_case_ids_in_domain(case_type)

        print("Creating tasks...")
        for case_id in with_progress_bar(case_ids):
            sync_case_for_messaging.delay(domain, case_id)
