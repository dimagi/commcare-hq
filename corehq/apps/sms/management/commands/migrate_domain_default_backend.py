from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SQLMobileBackendMapping, MigrationStatus
from corehq.apps.sms.signals import _sync_default_backend_mapping
from django.core.management.base import BaseCommand
from optparse import make_option


def balance(couch_count):
    sql_count = SQLMobileBackendMapping.objects.filter(is_global=False).count()
    print "%i / %i Total Domain Backend Mappings Migrated" % (sql_count, couch_count)

    if couch_count != sql_count:
        print "ERROR: Counts do not match. Please investigate before continuing."


def migrate(balance_only=False):
    if not MigrationStatus.has_migration_completed(MigrationStatus.MIGRATION_BACKEND):
        print ("ERROR: The backend migration (./manage.py migrate_backends_to_sql) "
               "must be completed before doing the domain default backend migration")
        return

    couch_count = 0
    for domain in Domain.get_all():
        if domain.default_sms_backend_id:
            couch_count += 1

        if not balance_only:
            _sync_default_backend_mapping(domain)

    balance(couch_count)
    if not balance_only:
        MigrationStatus.set_migration_completed(MigrationStatus.MIGRATION_DOMAIN_DEFAULT_BACKEND)


class Command(BaseCommand):
    args = ""
    help = ("Migrates Domain.default_sms_backend_id to a SQLMobileBackendMapping entry")
    option_list = BaseCommand.option_list + (
        make_option("--balance-only",
                    action="store_true",
                    dest="balance_only",
                    default=False,
                    help="Include this option to only run the balancing step."),
    )

    def handle(self, *args, **options):
        migrate(balance_only=options['balance_only'])
