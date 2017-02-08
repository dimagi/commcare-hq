from copy import deepcopy
from optparse import make_option

from django.core.management import BaseCommand, CommandError

from corehq.pillows.app_submission_tracker import (
    get_couch_app_form_submission_tracker_reindexer,
    get_sql_app_form_submission_tracker_reindexer
)
from corehq.pillows.application import get_app_reindexer
from corehq.pillows.case import (
    get_couch_case_reindexer, get_sql_case_reindexer
)
from corehq.pillows.case_search import get_case_search_reindexer
from corehq.pillows.domain import get_domain_reindexer
from corehq.pillows.group import get_group_reindexer
from corehq.pillows.groups_to_user import get_groups_to_user_reindexer
from corehq.pillows.ledger import get_ledger_v2_reindexer, get_ledger_v1_reindexer
from corehq.pillows.reportcase import get_report_case_reindexer
from corehq.pillows.reportxform import get_report_xforms_reindexer
from corehq.pillows.sms import get_sms_reindexer
from corehq.pillows.user import get_user_reindexer
from corehq.pillows.xform import get_couch_form_reindexer, get_sql_form_reindexer

REINDEX_FNS = {
    'domain': get_domain_reindexer,
    'user': get_user_reindexer,
    'group': get_group_reindexer,
    'groups-to-user': get_groups_to_user_reindexer,
    'case': get_couch_case_reindexer,
    'form': get_couch_form_reindexer,
    'sql-case': get_sql_case_reindexer,
    'sql-form': get_sql_form_reindexer,
    'case-search': get_case_search_reindexer,
    'ledger-v2': get_ledger_v2_reindexer,
    'ledger-v1': get_ledger_v1_reindexer,
    'sms': get_sms_reindexer,
    'report-case': get_report_case_reindexer,
    'report-xform': get_report_xforms_reindexer,
    'app': get_app_reindexer,
    'couch-app-form-submission': get_couch_app_form_submission_tracker_reindexer,
    'sql-app-form-submission': get_sql_app_form_submission_tracker_reindexer,
}


class Command(BaseCommand):
    help = 'Reindex a pillowtop index'

    def add_arguments(self, parser):
        parser.add_argument('index')
        parser.add_argument(
            '--cleanup',
            action='store_true',
            dest='cleanup',
            default=False,
            help='Clean index (delete data) before reindexing.'
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )

        # for resumable reindexers
        parser.add_argument(
            '--reset',
            action='store_true',
            dest='reset',
            help='Reset a resumable reindex'
        )
        parser.add_argument(
            '--chunksize',
            type=int,
            action='store',
            dest='chunksize',
            help='Number of docs to process at a time'
        )

        # for ES reindexers
        parser.add_argument(
            '--in-place',
            action='store_true',
            dest='in-place',
            help='Run the reindex in place - assuming it is against a live index.'
        )

    def handle(self, index, *args, **options):
        cleanup = options.pop('cleanup')
        noinput = options.pop('noinput')
        if index not in REINDEX_FNS:
            raise CommandError('Supported indices to reindex are: {}'.format(','.join(REINDEX_FNS.keys())))

        def confirm():
            return raw_input("Are you sure you want to delete the current index (if it exists)? y/n\n") == 'y'

        reindexer = REINDEX_FNS[index]()
        reindexer_options = {
            key: value for key, value in options.items()
            if value is not None
        }
        reindexer.consume_options(reindexer_options)

        if cleanup and (noinput or confirm()):
            reindexer.clean()

        reindexer.reindex()
