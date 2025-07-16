from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.tasks import _refresh_data_dictionary_from_app
from corehq.apps.data_cleaning.utils.cases import (
    clear_caches_case_data_cleaning,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    get_migration_complete,
    get_migration_status,
    set_migration_complete,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.models import MigrationStatus
from corehq.util.log import with_progress_bar

MIGRATION_SLUG = "refresh_data_dictionary"


class Command(BaseCommand):
    help = 'Refreshes data dictionary for all domains and their apps. ' \
           'For specific domains, ./manage.py refresh_data_dictionary domain1 domain2'

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*',
            help="Domain name(s). If blank, will refresh for all domains")

    def handle(self, **options):
        migration_status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if migration_status == MigrationStatus.COMPLETE:
            print("Migration already complete")
            return
        elif migration_status == MigrationStatus.NOT_STARTED:
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        domains = options['domains'] or Domain.get_all_names()
        success = True

        for domain in with_progress_bar(domains):
            if get_migration_complete(domain, MIGRATION_SLUG):
                continue
            set_migration_started(domain, MIGRATION_SLUG)
            try:
                apps = get_apps_in_domain(domain)
            except Exception as e:
                print(f'Failed to get apps in domain {domain}: {str(e)}')
                success = False
                continue

            domain_success = True
            for app in apps:
                try:
                    _refresh_data_dictionary_from_app(domain, app.get_id)
                except Exception as e:
                    print(f'Failed to refresh app {app.get_id} in domain {domain}: {str(e)}')
                    success = False
                    domain_success = False

            clear_caches_case_data_cleaning(domain)
            if domain_success:
                set_migration_complete(domain, MIGRATION_SLUG)

        if success and not options['domains']:
            set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
            print("All domains and apps processed successfully!")
