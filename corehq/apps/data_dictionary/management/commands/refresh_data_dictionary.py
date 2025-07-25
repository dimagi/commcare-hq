from django.core.management.base import BaseCommand, CommandError

from jsonobject.exceptions import BadValueError

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
    help = (
        "Refreshes data dictionary for all domains and their apps. "
        "This command will not re-run on domains that have already been processed and marked as complete. "
        "Use --domain-to-skip and --app-id-to-skip to skip known bad domains or apps."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain-to-skip',
            nargs='*',
            default=[],
            help="Domain(s) to skip (e.g. malformed domains), separated by commas"
        )
        parser.add_argument(
            '--app-id-to-skip',
            nargs='*',
            default=[],
            help="App ID(s) to skip (e.g. malformed apps), separated by commas"
        )

    def handle(self, **options):
        migration_status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if migration_status == MigrationStatus.COMPLETE:
            print("Migration already complete")
            return
        elif migration_status == MigrationStatus.NOT_STARTED:
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        domains_to_skip = set(options['domain_to_skip'])
        app_ids_to_skip = set(options['app_id_to_skip'])

        all_domains = Domain.get_all_names()

        for domain in with_progress_bar(all_domains):
            if domain in domains_to_skip:
                print(f"[Domain: {domain}] Skipping domain")
                set_migration_complete(domain, MIGRATION_SLUG)
                continue
            if get_migration_complete(domain, MIGRATION_SLUG):
                continue
            set_migration_started(domain, MIGRATION_SLUG)
            try:
                apps = get_apps_in_domain(domain)
            except Exception as e:
                if isinstance(e, BadValueError) and "does not comply with the x.y.z schema" in str(e):
                    print(f"[Domain: {domain}] Skipping this domain because it has app "
                          f"referencing unsupported CommCare Version: {e}")
                    set_migration_complete(domain, MIGRATION_SLUG)
                    continue
                raise CommandError(
                    f"[Domain: {domain}] Failed to get apps: {e}\n"
                    "If you believe this is due to the apps in this domain being malformed, "
                    "rerun the command and add the domain to the --domain-to-skip flag"
                )

            for app in apps:
                if app.get_id in app_ids_to_skip:
                    print(f"[Domain: {domain}] Skipping app {app.get_id}")
                    continue
                try:
                    _refresh_data_dictionary_from_app(domain, app.get_id)
                except Exception as e:
                    raise CommandError(
                        f"[Domain: {domain}] Failed to refresh app {app.get_id}: {e}\n"
                        "If you believe this is due to this app being malformed, "
                        "rerun the command and add the app id to --app-id-to-skip."
                    )

            clear_caches_case_data_cleaning(domain)
            set_migration_complete(domain, MIGRATION_SLUG)

        set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
        print("All valid domains and apps processed successfully!")
