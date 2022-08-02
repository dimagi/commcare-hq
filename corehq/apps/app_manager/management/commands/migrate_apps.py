from corehq.apps.builds.models import BuildSpec
from corehq.toggles import SYNC_SEARCH_CASE_CLAIM

from django.core.management.base import BaseCommand
from corehq.apps.app_manager.models import Application

from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids


class Command(BaseCommand):
    """
    Migrates any app to latest version
    """

    def add_arguments(self, parser):
        parser.add_argument('version')
        # parser.add_argument('')

    def handle(self, version, **options):
        new_build_spec = BuildSpec.from_string(f"{version}/latest")
        domains = sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains())
        for domain in domains:
            print(f"Current domain: {domain}")
            app_ids = get_all_app_ids(domain)  # , include_builds=True)
            print(f"Apps found: {len(app_ids)}")

            for app_id in app_ids:
                apps_to_migrate = []
                app = Application.get(app_id)
                if app['build_spec'].version != version:
                    apps_to_migrate.append(app)

            # if there are no apps in the domain needing to be migrated we skip the domain
            if len(apps_to_migrate) == 0:
                print(f"No apps to migrate in domain: {domain}")
                continue

            print(f"Apps to migrate: {len(apps_to_migrate)}")

            for i, current_app in enumerate(apps_to_migrate):
                current_app.build_spec = new_build_spec
                errors = current_app.validate_app()
                if errors:
                    # do something here with unvalidated app
                    continue
                current_app.save()

                # progress bar
                print("   Migrating apps %d/%d [%-20s] %d%%" %
                    (i + 1, len(apps_to_migrate), '=' * int((20 * (i / len(apps_to_migrate)))),
                    (i / len(apps_to_migrate)) * 100), end="\r")
            print()  # prevents the progress bar from deleting from the console, for debugging
