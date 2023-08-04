from django.core.management import BaseCommand

from corehq.apps.es.transient_util import (
    doc_adapter_from_cname,
    iter_doc_adapters,
)
from pillowtop.reindexer.reindexer import (
    prepare_index_for_reindex,
    prepare_index_for_usage,
    clean_index
)
from corehq.apps.es.transient_util import iter_index_cnames


class Command(BaseCommand):
    help = """
        Initialize all or any one specific elasticsearch indices
        and prepare them for reindex
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--index',
            help='Specify any one hq index cannonical name instead of the default all',
            choices=list(iter_index_cnames())
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
            doc_adapters = [doc_adapter_from_cname(index)]
        else:
            doc_adapters = iter_doc_adapters()
        for adapter in doc_adapters:
            if set_for_usage:
                prepare_index_for_usage(adapter.index_name)
            else:
                if reset:
                    clean_index(adapter.index_name)
                prepare_index_for_reindex(adapter)
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
