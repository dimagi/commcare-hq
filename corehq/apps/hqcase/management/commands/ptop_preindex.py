from datetime import datetime

from django.conf import settings
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

import gevent

from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import (
    DomainReindexerFactory,
    UserReindexerFactory,
    GroupReindexerFactory,
    GroupToUserReindexerFactory,
    SqlCaseReindexerFactory,
    SqlFormReindexerFactory,
    CaseSearchReindexerFactory,
    SmsReindexerFactory,
    AppReindexerFactory,
)
from corehq.apps.es.client import manager
from corehq.pillows.user import add_demo_user_to_user_index
from corehq.pillows.utils import get_all_expected_es_indices
from corehq.util.log import get_traceback_string
from corehq.apps.es.index.settings import IndexSettingsKey
from pillowtop.reindexer.reindexer import ReindexerFactory


def get_reindex_commands(hq_index_name):
    """Return a list of ``ReindexerFactory`` classes or functions that are used
    to rebuild the index from scratch.

    :param hq_index_name: ``str`` name of the Elastic index alias"""
    pillow_command_map = {
        IndexSettingsKey.DOMAINS: [DomainReindexerFactory],
        IndexSettingsKey.CASES: [SqlCaseReindexerFactory],
        IndexSettingsKey.FORMS: [SqlFormReindexerFactory],
        # groupstousers indexing must happen after all users are indexed
        IndexSettingsKey.USERS: [
            UserReindexerFactory,
            add_demo_user_to_user_index,
            GroupToUserReindexerFactory,
        ],
        IndexSettingsKey.APPS: [AppReindexerFactory],
        IndexSettingsKey.GROUPS: [GroupReindexerFactory],
        IndexSettingsKey.CASE_SEARCH: [CaseSearchReindexerFactory],
        IndexSettingsKey.SMS: [SmsReindexerFactory],
    }
    return pillow_command_map.get(hq_index_name, [])


def do_reindex(hq_index_name, reset):
    print("Starting pillow preindex %s" % hq_index_name)
    reindex_commands = get_reindex_commands(hq_index_name)
    for factory_or_func in reindex_commands:
        if isinstance(factory_or_func, type):
            if not issubclass(factory_or_func, ReindexerFactory):
                raise ValueError(f"expected ReindexerFactory, got: {factory_or_func!r}")
            kwargs = {}
            reindex_args = ReindexerFactory.resumable_reindexer_args
            if reset \
                    and factory_or_func.arg_contributors \
                    and reindex_args in factory_or_func.arg_contributors:
                kwargs["reset"] = True
            factory_or_func(**kwargs).build().reindex()
        else:
            factory_or_func()
    print("Pillow preindex finished %s" % hq_index_name)


class Command(BaseCommand):
    help = """
    Create all ES indexes that exist in code, but do not exist in the cluster.
    For indexes that already exist, this command does nothing unless --reset is passed
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            dest='reset',
            default=False,
            help='Reset resumable indices. Results in all documents being reprocessed for this index',
        )

    def handle(self, **options):
        runs = []
        all_es_index_adapters = list(get_all_expected_es_indices())

        if options['reset']:
            indices_needing_reindex = all_es_index_adapters
        else:
            indices_needing_reindex = [
                adapter for adapter in all_es_index_adapters
                if not manager.index_exists(adapter.index_name)
            ]
            if not indices_needing_reindex:
                print('Nothing needs to be reindexed')
                return

        print("Reindexing:\n\t", end=' ')
        print('\n\t'.join(map(str, indices_needing_reindex)))

        preindex_message = """
        Heads up!

        %s is going to start preindexing the following indices:\n
        %s

        This may take a while, so don't deploy until all these have reported finishing.
            """ % (
            settings.EMAIL_SUBJECT_PREFIX,
            '\n\t'.join(map(str, indices_needing_reindex))
        )

        mail_admins("Pillow preindexing starting", preindex_message)
        start = datetime.utcnow()
        for adapter in indices_needing_reindex:
            # loop through pillows once before running greenlets
            # to fail hard on misconfigured pillows
            reindex_commands = get_reindex_commands(adapter.settings_key)
            if not reindex_commands:
                raise Exception(
                    "Error, pillow [%s] is not configured "
                    "with its own management command reindex command "
                    "- it needs one" % adapter.settings_key
                )

        for adapter in indices_needing_reindex:
            print(adapter.settings_key)
            g = gevent.spawn(do_reindex, adapter.settings_key, options['reset'])
            runs.append(g)

        if len(indices_needing_reindex) > 0:
            gevent.joinall(runs)
            try:
                for job in runs:
                    job.get()
            except Exception:
                mail_admins("Pillow preindexing failed", get_traceback_string())
                raise
            else:
                mail_admins(
                    "Pillow preindexing completed",
                    "Reindexing %s took %s seconds" % (
                        ', '.join(map(str, indices_needing_reindex)),
                        (datetime.utcnow() - start).seconds
                    )
                )

        print("All pillowtop reindexing jobs completed")
