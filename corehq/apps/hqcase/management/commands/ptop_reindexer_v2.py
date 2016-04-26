from optparse import make_option
from django.core.management import BaseCommand, CommandError
from corehq.pillows.case import get_couch_case_reindexer, get_sql_case_reindexer
from corehq.pillows.case_search import get_case_search_reindexer
from corehq.pillows.domain import get_domain_reindexer
from corehq.pillows.group import get_group_reindexer
from corehq.pillows.groups_to_user import get_groups_to_user_reindexer
from corehq.pillows.user import get_user_reindexer
from corehq.pillows.xform import get_couch_form_reindexer, get_sql_form_reindexer


class Command(BaseCommand):
    args = 'index'
    help = 'Reindex a pillowtop index'

    option_list = BaseCommand.option_list + (
        make_option('--cleanup',
                    action='store_true',
                    dest='cleanup',
                    default=False,
                    help='Clean index (delete data) before reindexing.'),
        make_option('--noinput',
                    action='store_true',
                    dest='noinput',
                    default=False,
                    help='Skip important confirmation warnings.'),
    )

    def handle(self, index, *args, **options):
        cleanup = options['cleanup']
        noinput = options['noinput']
        reindex_fns = {
            'domain': get_domain_reindexer,
            'user': get_user_reindexer,
            'group': get_group_reindexer,
            'groups-to-user': get_groups_to_user_reindexer,
            'case': get_couch_case_reindexer,
            'form': get_couch_form_reindexer,
            'sql-case': get_sql_case_reindexer,
            'sql-form': get_sql_form_reindexer,
            'case-search': get_case_search_reindexer
        }
        if index not in reindex_fns:
            raise CommandError('Supported indices to reindex are: {}'.format(','.join(reindex_fns.keys())))

        def confirm():
            return raw_input("Are you sure you want to delete the current index (if it exists)? y/n\n") == 'y'

        reindexer = reindex_fns[index]()
        if cleanup and (noinput or confirm()):
            reindexer.clean_index()

        reindexer.reindex()
