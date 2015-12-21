from corehq.apps.sms.mixin import BackendMapping
from corehq.apps.sms.models import SQLMobileBackendMapping, MigrationStatus
from django.core.management.base import BaseCommand
from optparse import make_option


def balance(couch_count):
    sql_count = SQLMobileBackendMapping.objects.count()
    print "%i / %i Total Backend Mappings Migrated" % (sql_count, couch_count)

    if couch_count != sql_count:
        print "ERROR: Counts do not match. Please investigate before continuing."


def migrate(balance_only=False):
    if not MigrationStatus.has_migration_completed('backend'):
        print ("ERROR: The backend migration (./manage.py migrate_backends_to_sql) "
               "must be completed before doing the backend mapping migration")
        return

    # There aren't a lot of backend mappings, no need to use iter_docs
    mappings = BackendMapping.view(
        'sms/backend_map',
        include_docs=True
    ).all()
    couch_count = 0
    for mapping in mappings:
        couch_count += 1
        if not balance_only:
            mapping._migration_do_sync()
    balance(couch_count)
    if not balance_only:
        MigrationStatus.set_migration_completed('backend_map')


class Command(BaseCommand):
    args = ""
    help = ("Migrates BackendMaping to SQLMobileBackendMapping")
    option_list = BaseCommand.option_list + (
        make_option("--balance-only",
                    action="store_true",
                    dest="balance_only",
                    default=False,
                    help="Include this option to only run the balancing step."),
    )

    def handle(self, *args, **options):
        migrate(balance_only=options['balance_only'])
