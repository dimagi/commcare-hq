from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SQLMobileBackend, SQLMobileBackendMapping, MigrationStatus
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


def balance(couch_count):
    sql_count = SQLMobileBackendMapping.objects.filter(is_global=False).count()
    print "%i / %i Total Domain Backend Mappings Migrated" % (sql_count, couch_count)

    if couch_count != sql_count:
        print "ERROR: Counts do not match. Please investigate before continuing."


def migrate(balance_only=False):
    if not MigrationStatus.has_migration_completed('backend'):
        print ("ERROR: The backend migration (./manage.py migrate_backends_to_sql) "
               "must be completed before doing the domain default backend migration")
        return

    couch_count = 0
    result = Domain.view('domain/domains', include_docs=False, reduce=False).all()
    ids = [row['id'] for row in result]

    for doc in iter_docs(Domain.get_db(), ids):
        backend_id = doc.get('default_sms_backend_id')
        domain = doc.get('name')

        if backend_id:
            couch_count += 1

            if not balance_only:
                try:
                    backend = SQLMobileBackend.objects.get(couch_id=backend_id)
                except SQLMobileBackend.DoesNotExist:
                    print "ERROR: Backend %s for domain %s not found" % (backend_id, domain)
                    continue

                SQLMobileBackendMapping(
                    is_global=False,
                    domain=domain,
                    backend_type='SMS',
                    prefix='*',
                    backend=backend
                ).save()

    balance(couch_count)
    if not balance_only:
        MigrationStatus.set_migration_completed('domain_default_backend')


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
