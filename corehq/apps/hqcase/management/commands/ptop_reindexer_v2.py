from django.core.management import BaseCommand, CommandError
from corehq.pillows.case import get_couch_case_reindexer, get_sql_case_reindexer
from corehq.pillows.xform import get_couch_form_reindexer, get_sql_form_reindexer


class Command(BaseCommand):
    args = 'index'
    help = 'Reindex a pillowtop index'

    def handle(self, index, *args, **options):
        reindex_fns = {
            'case': get_couch_case_reindexer,
            'form': get_couch_form_reindexer,
            'sql-case': get_sql_case_reindexer,
            'sql-form': get_sql_form_reindexer,
        }
        if index not in reindex_fns:
            raise CommandError('Supported indices to reindex are: {}'.format(','.join(reindex_fns.keys())))

        reindexer = reindex_fns[index]()
        reindexer.reindex()
