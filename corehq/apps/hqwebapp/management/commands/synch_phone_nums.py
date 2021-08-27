import time

from django.core.management.base import BaseCommand

from corehq.apps.sms.tasks import \
    sync_user_phone_numbers as sms_sync_user_phone_numbers
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    iter_all_rows,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.log import with_progress_bar

from couchforms.models import XFormInstance

from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider


class Command(BaseCommand):
    help = "Resync all contacts' phone numbers for given projects"

    def add_arguments(self, parser):
        parser.add_argument('-d', '--domains', type=str, help='Comma separated domain list')

    def handle(self, **kwargs):
        domains = kwargs['domains'].split(',')

        for domain in domains:
            print("Resync all contacts' phone numbers for project %s  " % domain)
            print("Synching for phone numbers")
            commcare_user_ids = (
                CommCareUser.ids_by_domain(domain, is_active=True) +
                CommCareUser.ids_by_domain(domain, is_active=False)
            )
            for user_id in with_progress_bar(commcare_user_ids):
                sms_sync_user_phone_numbers.delay(user_id)
            self.sync_cases(domain)

    def sync_cases(self, domain):
        db_aliases = get_db_aliases_for_partitioned_query()
        db_aliases.sort()

        if should_use_sql_backend(domain):
            case_accessor = CaseReindexAccessor(domain)
            case_ids = (case.case_id for case in iter_all_rows(case_accessor))
        else:
            changes = _iter_changes(domain, CASE_DOC_TYPES)
            case_ids = (case.id for case in changes)

        next_event = time.time() + 10
        for i, case_id in enumerate(case_ids):
            sync_case_for_messaging.delay(domain, case_id)

            if time.time() > next_event:
                print("Queued %d cases for domain %s" % (i + 1, domain))
                next_event = time.time() + 10


CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted']


def _iter_changes(domain, doc_types):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=doc_types,
    ).iter_all_changes()
