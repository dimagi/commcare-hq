from django.core.management import BaseCommand


from corehq.elastic import ES_META, get_es_new
from pillowtop.reindexer.reindexer import (
    prepare_index_for_reindex,
    prepare_index_for_usage,
    clean_index
)


class Command(BaseCommand):
    help = """
        Initialize all or any one specific elasticsearch indices
        and prepare them for reindex
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--index',
            help='Specify any one index instead of the default all'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            dest='reset',
            default=False,
            help='Delete existing indices before initializing.'
        )
        parser.add_argument(
            '--set-for-usage',
            action='store_true',
            dest='set_for_usage',
            default=False,
            help="""Set usage settings on indices that are already initialized.
                 By default, reindex settings are applied when index is initialized"""
        )

    def handle(self, index=None, reset=False, set_for_usage=False, **kwargs):
        es = get_es_new()
        if reset and not set_for_usage:
            confirm = input(
                """
                Are you sure you want to want to delete existing indices
                Note that this will delete any data in them. y/N?
                """
            )
            if confirm != "y":
                print("Cancelled by user.")
                return

        if index:
            indices = [ES_META[index]]
        else:
            indices = ES_META.values()
        for index in indices:
            if set_for_usage:
                prepare_index_for_usage(es, index)
            else:
                if reset:
                    clean_index(es, index)
                prepare_index_for_reindex(es, index)
        if set_for_usage:
            print("index ready for usage")
        else:
            print(
                """Initialized all indices and applied reindex settings
                After reindex is finished, you can run this command again
                with --set-for-usage to remove reindex settings and make it
                ready for usage.
                """
            )
