from __future__ import print_function
from __future__ import absolute_import
# http://www.gevent.org/gevent.monkey.html#module-gevent.monkey
from __future__ import unicode_literals
from gevent import monkey
monkey.patch_all()

import gevent
import six

from datetime import datetime
from six.moves import map

from django.core.mail import mail_admins
from django.core.management.base import BaseCommand
from django.conf import settings

from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import FACTORIES_BY_SLUG
from corehq.elastic import get_es_new
from corehq.pillows.user import add_demo_user_to_user_index
from corehq.pillows.utils import get_all_expected_es_indices
from corehq.util.log import get_traceback_string
from corehq.util.python_compatibility import soft_assert_type_text


def get_reindex_commands(alias_name):
    # pillow_command_map is a mapping from es pillows
    # to lists of management commands or functions
    # that should be used to rebuild the index from scratch
    pillow_command_map = {
        'hqdomains': ['domain'],
        'hqcases': ['case', 'sql-case'],
        'xforms': ['form', 'sql-form'],
        # groupstousers indexing must happen after all users are indexed
        'hqusers': [
            'user',
            add_demo_user_to_user_index,
            'groups-to-user',
        ],
        'hqapps': ['app'],
        'hqgroups': ['group'],
        'report_xforms': ['report-xform'],
        'report_cases': ['report-case'],
        'case_search': ['case-search'],
        'ledgers': ['ledger-v1', 'ledger-v2'],
        'smslogs': ['sms'],
    }
    return pillow_command_map.get(alias_name, [])


def do_reindex(alias_name, reset):
    print("Starting pillow preindex %s" % alias_name)
    reindex_commands = get_reindex_commands(alias_name)
    for reindex_command in reindex_commands:
        if isinstance(reindex_command, six.string_types):
            soft_assert_type_text(reindex_command)
            kwargs = {"reset": True} if reset else {}
            FACTORIES_BY_SLUG[reindex_command](**kwargs).build().reindex()
        else:
            reindex_command()
    print("Pillow preindex finished %s" % alias_name)


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
        print('\n\t'.join(map(six.text_type, indices_needing_reindex)))

        preindex_message = """
        Heads up!

        %s is going to start preindexing the following indices:\n
        %s

        This may take a while, so don't deploy until all these have reported finishing.
            """ % (
                settings.EMAIL_SUBJECT_PREFIX,
                '\n\t'.join(map(six.text_type, indices_needing_reindex))
            )

        mail_admins("Pillow preindexing starting", preindex_message)
        start = datetime.utcnow()
        for index_info in indices_needing_reindex:
            # loop through pillows once before running greenlets
            # to fail hard on misconfigured pillows
            reindex_command = get_reindex_commands(index_info.alias)
            if not reindex_command:
                raise Exception(
                    "Error, pillow [%s] is not configured "
                    "with its own management command reindex command "
                    "- it needs one" % index_info.alias
                )

        for index_info in indices_needing_reindex:
            print(index_info.alias)
            g = gevent.spawn(do_reindex, index_info.alias, options['reset'])
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
                        ', '.join(map(six.text_type, indices_needing_reindex)),
                        (datetime.utcnow() - start).seconds
                    )
                )

        print("All pillowtop reindexing jobs completed")
