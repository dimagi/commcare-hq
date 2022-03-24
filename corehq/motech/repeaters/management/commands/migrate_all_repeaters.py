import sys
import traceback

from django.core.management import call_command
from django.core.management.base import BaseCommand

from corehq.motech.repeaters.dbaccessors import get_all_repeater_docs
from corehq.motech.repeaters.models import SQLRepeater
from corehq.util.django_migrations import skip_on_fresh_install


class Command(BaseCommand):

    AUTO_MIGRATE_ITEMS_LIMIT = 2000

    @classmethod
    def count_items_to_be_migrated(cls):
        couch_count = len(get_all_repeater_docs())
        sql_count = SQLRepeater.objects.count()
        return couch_count - sql_count

    @classmethod
    def commit_adding_migration(cls):
        """
        This should be the merge commit of the pull request that adds the command to the commcare-hq repository.
        If this is provided, the failure message in migrate_from_migration will instruct users to deploy this
        commit before running the command.
        """
        return None

    @classmethod
    @skip_on_fresh_install
    def migrate_from_migration(cls, apps, schema_editor):
        """
            Should only be called from within a django migration.
            Calls sys.exit on failure.
        """
        to_migrate = cls.count_items_to_be_migrated()
        print(f"Found {to_migrate} Repeater documents to migrate.")

        migrated = to_migrate == 0
        if migrated:
            return

        command_name = cls.__module__.split('.')[-1]
        if to_migrate < cls.AUTO_MIGRATE_ITEMS_LIMIT:
            try:
                call_command(command_name)
                remaining = cls.count_items_to_be_migrated()
                if remaining != 0:
                    migrated = False
                    print(f"Automatic migration failed, {remaining} items remain to migrate.")
                else:
                    migrated = True
            except Exception:
                traceback.print_exc()
        else:
            print("Found {} items that need to be migrated.".format(to_migrate))
            print("Too many to migrate automatically.")

        if not migrated:
            print(f"""
                A migration must be performed before this environment can be upgraded to the latest version
                of CommCareHQ. This migration is run using the management command {command_name}.
            """)
            if cls.commit_adding_migration():
                print(f"""
                Run the following commands to run the migration and get up to date:

                    commcare-cloud <env> fab setup_limited_release --set code_branch={cls.commit_adding_migration()}

                    commcare-cloud <env> django-manage --release <release created by previous command> {command_name}

                    commcare-cloud <env> deploy commcare
                """)
            sys.exit(1)

    def add_arguments(self, parser):
        parser.add_argument(
            '--verify-only',
            action='store_true',
            dest='verify_only',
            default=False,
            help="""
                Don't migrate anything, instead check if couch and sql data is identical.
            """,
        )
        parser.add_argument(
            '--skip-verify',
            action='store_true',
            dest='skip_verify',
            default=False,
            help="""
                Migrate even if verifcation fails. This is intended for usage only with
                models that don't support verification.
            """,
        )

    def handle(self, **options):
        verify_only = options.get("verify_only", False)
        skip_verify = options.get("skip_verify", False)

        doc_count = len(get_all_repeater_docs())
        sql_doc_count = SQLRepeater.objects.count()

        print(f"Found {doc_count} Repeater docs and {sql_doc_count} SQL Repeater models")

        all_commands = ['migrate_shortformrepeater', 'migrate_createcaserepeater', 'migrate_refercaserrepeater',
        'migrate_dhis2repeater', 'migrate_formrepeater', 'migrate_userrepeater', 'migrate_fhirrepeater',
        'migrate_appstructurerepeater', 'migrate_caserepeater', 'migrate_caseexpressionrepeater',
        'migrate_dataregistrycaseupdaterepeater', 'migrate_dhis2entityrepeater', 'migrate_openmrsrepeater',
        'migrate_locationrepeater', 'migrate_updatecaserepeater']

        for cmd in all_commands:
            call_command(cmd, verify_only=verify_only, skip_verify=skip_verify)
