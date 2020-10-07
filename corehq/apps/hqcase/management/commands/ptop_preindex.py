# http://www.gevent.org/gevent.monkey.html#module-gevent.monkey
from datetime import datetime

from django.conf import settings
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

import gevent
from gevent import monkey

from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import (
    FACTORIES_BY_SLUG,
)
from corehq.elastic import get_es_new
from corehq.pillows.user import add_demo_user_to_user_index
from corehq.pillows.utils import get_all_expected_es_indices
from corehq.util.log import get_traceback_string
from pillowtop.es_utils import (
    XFORM_HQ_INDEX_NAME,
    CASE_HQ_INDEX_NAME,
    USER_HQ_INDEX_NAME,
    DOMAIN_HQ_INDEX_NAME,
    APP_HQ_INDEX_NAME,
    GROUP_HQ_INDEX_NAME,
    SMS_HQ_INDEX_NAME,
    REPORT_CASE_HQ_INDEX_NAME,
    REPORT_XFORM_HQ_INDEX_NAME,
    CASE_SEARCH_HQ_INDEX_NAME
)


monkey.patch_all()


def get_reindex_commands(hq_index_name):
    # pillow_command_map is a mapping from es pillows
    # to lists of management commands or functions
    # that should be used to rebuild the index from scratch
    pillow_command_map = {
        DOMAIN_HQ_INDEX_NAME: ['domain'],
        CASE_HQ_INDEX_NAME: ['case', 'sql-case'],
        XFORM_HQ_INDEX_NAME: ['form', 'sql-form'],
        # groupstousers indexing must happen after all users are indexed
        USER_HQ_INDEX_NAME: [
            'user',
            add_demo_user_to_user_index,
            'groups-to-user',
        ],
        APP_HQ_INDEX_NAME: ['app'],
        GROUP_HQ_INDEX_NAME: ['group'],
        REPORT_XFORM_HQ_INDEX_NAME: ['report-xform'],
        REPORT_CASE_HQ_INDEX_NAME: ['report-case'],
        CASE_SEARCH_HQ_INDEX_NAME: ['case-search'],
        SMS_HQ_INDEX_NAME: ['sms'],
    }
    return pillow_command_map.get(hq_index_name, [])


def do_reindex(hq_index_name, reset):
    print("Starting pillow preindex %s" % hq_index_name)
    reindex_commands = get_reindex_commands(hq_index_name)
    for reindex_command in reindex_commands:
        if isinstance(reindex_command, str):
            kwargs = {"reset": True} if reset else {}
            FACTORIES_BY_SLUG[reindex_command](**kwargs).build().reindex()
        else:
            reindex_command()
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
        all_es_indices = get_all_expected_es_indices()
        es = get_es_new()
        indices_needing_reindex = [info for info in all_es_indices if not es.indices.exists(info.index)]

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
        for index_info in indices_needing_reindex:
            # loop through pillows once before running greenlets
            # to fail hard on misconfigured pillows
            reindex_command = get_reindex_commands(index_info.hq_index_name)
            if not reindex_command:
                raise Exception(
                    "Error, pillow [%s] is not configured "
                    "with its own management command reindex command "
                    "- it needs one" % index_info.hq_index_name
                )

        for index_info in indices_needing_reindex:
            print(index_info.hq_index_name)
            g = gevent.spawn(do_reindex, index_info.hq_index_name, options['reset'])
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
