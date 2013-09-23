from datetime import datetime
from optparse import make_option
from django.core.mail import mail_admins
from gevent import monkey;monkey.patch_all()
import gevent
from pillowtop.listener import AliasedElasticPillow
from pillowtop.management.pillowstate import get_pillow_states
from pillowtop.run_pillowtop import import_pillows
from django.core.management.base import NoArgsCommand, BaseCommand
from django.core.management import call_command
from django.conf import settings


def get_reindex_command(pillow_class_name):
    pillow_command_map = {
        'DomainPillow': 'ptop_fast_reindex_domains',
        'CasePillow': 'ptop_fast_reindex_cases',
        'FullCasePillow': 'ptop_fast_reindex_fullcases',
        'XFormPillow': 'ptop_fast_reindex_xforms',
        'FullXFormPillow': 'ptop_fast_reindex_fullxforms',
        'UserPillow': 'ptop_fast_reindex_users',
        'AppPillow': 'ptop_fast_reindex_apps',
        'ReportXFormPillow': 'ptop_fast_reindex_reportxforms',
        'ReportCasePillow': 'ptop_fast_reindex_reportcases',
    }
    reindex_command = pillow_command_map.get(pillow_class_name, None)
    return reindex_command

def do_reindex(pillow_class_name):
    print "Starting pillow preindex %s" % pillow_class_name
    reindex_command = get_reindex_command(pillow_class_name)
    if reindex_command:
        call_command(reindex_command, **{'noinput': True, 'bulk': True})
        print "Pillow preindex finished %s" % pillow_class_name


class Command(BaseCommand):
    help = "Preindex ES pillows. Only run reindexer if the index doesn't exist."
    option_list = NoArgsCommand.option_list + (
        make_option('--replace',
                    action='store_true',
                    dest='replace',
                    default=False,
                    help='Reindex existing indices even if they are already there.'),
    )

    def handle(self, *args, **options):
        runs = []
        pillow_classes = import_pillows(instantiate=False)
        aliased_classes = filter(lambda x: issubclass(x, AliasedElasticPillow), pillow_classes)
        aliasable_pillows = [p(create_index=False) for p in aliased_classes]

        reindex_all = options['replace']

        mapped_masters, unmapped_masters, stale_indices = get_pillow_states(aliasable_pillows)

        # mapped masters: ES indices as known in the current running code state that
        # correctly have the alias applied to them

        # unmapped masters: ES indices as known in the current running code state that
        # do not have the alias applied to them

        # stale indices: ES indices running on ES that are not part of the current source control.

        print "Master indices missing aliases:"
        unmapped_indices = [x[0] for x in unmapped_masters]
        print unmapped_indices

        if reindex_all:
            print "Reindexing ALL master pillows that are not aliased"
            preindexable_pillows = aliasable_pillows
        else:
            print "Reindexing master pillows that do not exist yet (ones with aliases skipped)"
            preindexable_pillows = filter(lambda x: not x.index_exists(), aliasable_pillows)


        reindex_pillows = filter(lambda x: x.es_index in unmapped_indices, preindexable_pillows)

        print "Reindexing:\n\t%s" % '\n\t'.join(x.es_index for x in reindex_pillows)

        if len(reindex_pillows) > 0:
            preindex_message = """
        Heads up!

        %sis going to start preindexing the following pillows:
        %s

        This may take a while, so don't deploy until all these have reported finishing.
            """ % (settings.EMAIL_SUBJECT_PREFIX, ', '.join([x.__class__.__name__ for x in reindex_pillows]))

            mail_admins("Pillow preindexing starting", preindex_message)

        start = datetime.utcnow()
        for pillow in reindex_pillows:
            #loop through pillows once before running greenlets to fail hard on misconfigured pillows
            pillow_class_name = pillow.__class__.__name__
            reindex_command = get_reindex_command(pillow_class_name)
            if not reindex_command:
                raise Exception("Error, pillow [%s] is not configured with its own management command reindex command - it needs one" % pillow_class_name)

        for pillow in reindex_pillows:
            print pillow.__class__.__name__
            g = gevent.spawn(do_reindex, pillow.__class__.__name__)
            runs.append(g)
        gevent.joinall(runs)
        if len(reindex_pillows) > 0:
            mail_admins("Pillow preindexing completed", "Reindexing %s took %s seconds" % (
                ', '.join([x.__class__.__name__ for x in reindex_pillows]),
                (datetime.utcnow() - start).seconds
            ))
        print "All pillowtop reindexing jobs completed"







