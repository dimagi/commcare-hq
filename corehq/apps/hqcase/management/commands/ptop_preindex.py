from gevent import monkey; monkey.patch_all()
from pillowtop.es_utils import pillow_index_exists

from cStringIO import StringIO
import traceback
from datetime import datetime
from optparse import make_option
from django.core.mail import mail_admins
from pillowtop import get_all_pillow_classes
from corehq.pillows.user import add_demo_user_to_user_index
import gevent
from pillowtop.listener import AliasedElasticPillow
from pillowtop.management.pillowstate import get_pillow_states
from django.core.management.base import NoArgsCommand, BaseCommand
from django.core.management import call_command
from django.conf import settings


def get_reindex_commands(pillow_class_name):
    # pillow_command_map is a mapping from es pillows
    # to lists of management commands or functions
    # that should be used to rebuild the index from scratch
    pillow_command_map = {
        'DomainPillow': ['ptop_fast_reindex_domains'],
        'CasePillow': ['ptop_fast_reindex_cases'],
        'XFormPillow': ['ptop_fast_reindex_xforms'],
        # groupstousers indexing must happen after all users are indexed
        'UserPillow': [
            'ptop_fast_reindex_users',
            add_demo_user_to_user_index,
            'ptop_fast_reindex_groupstousers',
            'ptop_fast_reindex_unknownusers',
        ],
        'AppPillow': ['ptop_fast_reindex_apps'],
        'GroupPillow': ['ptop_fast_reindex_groups'],
        'SMSPillow': ['ptop_fast_reindex_smslogs'],
        'ReportXFormPillow': ['ptop_fast_reindex_reportxforms'],
        'ReportCasePillow': ['ptop_fast_reindex_reportcases'],
    }
    return pillow_command_map.get(pillow_class_name, [])


def do_reindex(pillow_class_name):
    print "Starting pillow preindex %s" % pillow_class_name
    reindex_commands = get_reindex_commands(pillow_class_name)
    for reindex_command in reindex_commands:
        if isinstance(reindex_command, basestring):
            call_command(reindex_command, **{'noinput': True, 'bulk': True})
        else:
            reindex_command()
    print "Pillow preindex finished %s" % pillow_class_name


class Command(BaseCommand):
    help = ("Preindex ES pillows. "
            "Only run reindexer if the index doesn't exist.")
    option_list = NoArgsCommand.option_list + (
        make_option(
            '--replace',
            action='store_true',
            dest='replace',
            default=False,
            help='Reindex existing indices even if they are already there.',
        ),
    )

    def handle(self, *args, **options):
        runs = []
        pillow_classes = get_all_pillow_classes()
        aliased_classes = filter(lambda x: issubclass(x, AliasedElasticPillow),
                                 pillow_classes)
        aliasable_pillows = [p(create_index=False) for p in aliased_classes]

        reindex_all = options['replace']

        pillow_state_results = get_pillow_states(aliasable_pillows)

        print "Master indices missing aliases:"
        unmapped_indices = [x[0] for x in pillow_state_results.unmapped_masters]
        print unmapped_indices

        if reindex_all:
            print "Reindexing ALL master pillows that are not aliased"
            preindexable_pillows = aliasable_pillows
        else:
            print ("Reindexing master pillows that do not exist yet "
                   "(ones with aliases skipped)")

            preindexable_pillows = filter(pillow_index_exists, aliasable_pillows)

        reindex_pillows = filter(lambda x: x.es_index in unmapped_indices,
                                 preindexable_pillows)

        print "Reindexing:\n\t",
        print '\n\t'.join(x.es_index for x in reindex_pillows)

        if len(reindex_pillows) > 0:
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
            pillow_class_name = pillow.__class__.__name__
            reindex_command = get_reindex_commands(pillow_class_name)
            if not reindex_command:
                raise Exception(
                    "Error, pillow [%s] is not configured "
                    "with its own management command reindex command "
                    "- it needs one" % pillow_class_name
                )

        for pillow in reindex_pillows:
            print pillow.__class__.__name__
            g = gevent.spawn(do_reindex, pillow.__class__.__name__)
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
