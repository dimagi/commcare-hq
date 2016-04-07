from gevent import monkey; monkey.patch_all()
from corehq.elastic import get_es_new


from pillowtop.es_utils import get_all_elasticsearch_pillow_classes, get_all_expected_es_indices


from cStringIO import StringIO
import traceback
from datetime import datetime
from django.core.mail import mail_admins
from corehq.pillows.user import add_demo_user_to_user_index
import gevent
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


def get_reindex_commands(alias_name):
    # pillow_command_map is a mapping from es pillows
    # to lists of management commands or functions
    # that should be used to rebuild the index from scratch
    pillow_command_map = {
        'hqdomains': ['ptop_fast_reindex_domains'],
        'hqcases': ['ptop_fast_reindex_cases'],
        'xforms': ['ptop_fast_reindex_xforms'],
        # groupstousers indexing must happen after all users are indexed
        'hqusers': [
            'ptop_fast_reindex_users',
            add_demo_user_to_user_index,
            'ptop_fast_reindex_groupstousers',
            # 'ptop_fast_reindex_unknownusers',  removed until we have a better workflow for this
        ],
        'hqapps': ['ptop_fast_reindex_apps'],
        'hqgroups': ['ptop_fast_reindex_groups'],
        'report_xforms': ['ptop_fast_reindex_reportxforms'],
        'report_cases': ['ptop_fast_reindex_reportcases'],
    }
    return pillow_command_map.get(alias_name, [])


def do_reindex(alias_name):
    print "Starting pillow preindex %s" % alias_name
    reindex_commands = get_reindex_commands(alias_name)
    for reindex_command in reindex_commands:
        if isinstance(reindex_command, basestring):
            call_command(reindex_command, **{'noinput': True, 'bulk': True})
        else:
            reindex_command()
    print "Pillow preindex finished %s" % alias_name


class Command(BaseCommand):
    help = ("Preindex ES pillows. "
            "Only run reindexer if the index doesn't exist.")

    def handle(self, *args, **options):
        runs = []
        aliased_classes = get_all_elasticsearch_pillow_classes()
        all_es_indices = get_all_expected_es_indices()
        es = get_es_new()
        indices_needing_reindex = [info for info in all_es_indices if not es.indices.exists(info.index)]

        if not indices_needing_reindex:
            print 'Nothing needs to be reindexed'
            return

        aliasable_pillows = [p(online=False) for p in aliased_classes]
        index_names_needing_reindex = [info.index for info in indices_needing_reindex]

        print "Reindexing:\n\t",
        print '\n\t'.join(index_names_needing_reindex)

        reindex_pillows = filter(lambda x: x.es_index in index_names_needing_reindex, aliasable_pillows)
        preindex_message = """
        Heads up!

        %s is going to start preindexing the following pillows:
        %s

        This may take a while, so don't deploy until all these have reported finishing.
            """ % (
                settings.EMAIL_SUBJECT_PREFIX,
                ', '.join([x.__class__.__name__ for x in reindex_pillows])
            )

        mail_admins("Pillow preindexing starting", preindex_message)

        start = datetime.utcnow()
        for pillow in reindex_pillows:
            # loop through pillows once before running greenlets
            # to fail hard on misconfigured pillows
            reindex_command = get_reindex_commands(pillow.es_alias)
            if not reindex_command:
                raise Exception(
                    "Error, pillow [%s] is not configured "
                    "with its own management command reindex command "
                    "- it needs one" % pillow.es_alias
                )

        for pillow in reindex_pillows:
            print pillow.es_alias
            g = gevent.spawn(do_reindex, pillow.es_alias)
            runs.append(g)

        if len(reindex_pillows) > 0:
            gevent.joinall(runs)
            try:
                for job in runs:
                    job.get()
            except Exception:
                f = StringIO()
                traceback.print_exc(file=f)
                mail_admins("Pillow preindexing failed", f.getvalue())
                raise
            else:
                mail_admins(
                    "Pillow preindexing completed",
                    "Reindexing %s took %s seconds" % (
                        ', '.join([x.__class__.__name__ for x in reindex_pillows]),
                        (datetime.utcnow() - start).seconds
                    )
                )

        print "All pillowtop reindexing jobs completed"
