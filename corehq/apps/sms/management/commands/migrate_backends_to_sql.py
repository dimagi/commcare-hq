from corehq.apps.sms.mixin import MobileBackend
from corehq.apps.sms.models import SQLMobileBackend, SMS
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


def balance(couch_count, couch_count_deleted, couch_count_global):
    sql_count = SQLMobileBackend.objects.count()
    sql_count_deleted = SQLMobileBackend.objects.filter(deleted=True).count()
    sql_count_global = SQLMobileBackend.objects.filter(is_global=True).count()

    print "%i / %i Total Backends Migrated" % (sql_count, couch_count)
    print "%i / %i Deleted Backends Migrated" % (sql_count_deleted, couch_count_deleted)
    print "%i / %i Global Backends Migrated" % (sql_count_global, couch_count_global)

    if (
        (couch_count != sql_count) or
        (couch_count_deleted != sql_count_deleted) or
        (couch_count_global != sql_count_global)
    ):
        print ("ERROR: One or more of the counts above do not match. "
               "Please investigate before continuing.")


def get_backend_ids_from_result(result):
    return [item['id'] for item in result]


def check_that_backends_were_migrated(backend_ids):
    for backend_id in backend_ids:
        if not backend_id:
            continue
        try:
            SQLMobileBackend.objects.get(couch_id=backend_id)
        except SQLMobileBackend.DoesNotExist:
            print "ERROR: Backend %s has not been migrated" % backend_id


def check_active_backends():
    print "Checking all active backends are migrated..."
    backend_ids = []
    backend_ids.extend(
        get_backend_ids_from_result(
            MobileBackend.view(
                'sms/backend_by_owner_domain',
                include_docs=False
            ).all()
        )
    )
    backend_ids.extend(
        get_backend_ids_from_result(
            MobileBackend.view(
                'sms/global_backends',
                include_docs=False,
                reduce=False
            ).all()
        )
    )
    check_that_backends_were_migrated(backend_ids)


def check_historical_references():
    print "Checking all backends referenced historically are migrated..."
    backend_ids = SMS.objects.values_list('backend_id', flat=True).distinct()
    check_that_backends_were_migrated(backend_ids)


def perform_sanity_checks():
    """
    Performs a few sanity checks to be extra sure we didn't miss anything.
    """
    check_active_backends()
    check_historical_references()


def migrate(balance_only=False):
    couch_count = 0
    couch_count_deleted = 0
    couch_count_global = 0

    doc_types = [
        'KooKooBackend',
        'AppositBackend',
        'GrapevineBackend',
        'HttpBackend',
        'MachBackend',
        'MegamobileBackend',
        'SMSGHBackend',
        'TelerivetBackend',
        'TestSMSBackend',
        'TropoBackend',
        'TwilioBackend',
        'UnicelBackend',
    ]
    for doc_type in doc_types:
        # There aren't a lot of backends, no need to use iter_docs
        backends = MobileBackend.view(
            'all_docs/by_doc_type',
            startkey=[doc_type],
            endkey=[doc_type, {}],
            include_docs=True,
            reduce=False
        ).all()
        for backend in backends:
            couch_count += 1
            if backend.base_doc.endswith('-Deleted'):
                couch_count_deleted += 1
            if backend.is_global:
                couch_count_global += 1
            if not balance_only:
                backend.wrap_correctly()._migration_do_sync()
    perform_sanity_checks()
    balance(couch_count, couch_count_deleted, couch_count_global)


class Command(BaseCommand):
    args = ""
    help = ("Migrates MobileBackend to SQLMobileBackend")
    option_list = BaseCommand.option_list + (
        make_option("--balance-only",
                    action="store_true",
                    dest="balance_only",
                    default=False,
                    help="Include this option to only run the balancing step."),
    )

    def handle(self, *args, **options):
        migrate(balance_only=options['balance_only'])
