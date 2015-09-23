from pillowtop.run_pillowtop import start_pillows, start_pillow

from optparse import make_option
import sys
from django.conf import settings
from pillowtop.utils import import_pillow_string, get_all_pillows
from django.core.management.base import NoArgsCommand


class Command(NoArgsCommand):
    help = "Run pillows pillows listed in settings."
    option_list = NoArgsCommand.option_list + (
        make_option('--all',
                    action='store_true',
                    dest='run_all',
                    default=False,
                    help="Run all pillows from settings - use for local dev"),
        make_option('--list',
                    action='store_true',
                    dest='list_all',
                    default=False,
                    help="List pillowtop names"),
        make_option('--list-checkpoints',
                    action='store_true',
                    dest='list_checkpoints',
                    default=False,
                    help="Print all pillow doc ids."),
        make_option('--pillow-key',
                    action='store',
                    dest='pillow_key',
                    default=None,
                    help="Run a specific key of a group of pillows from settings.PILLOWTOPS list"),
        make_option('--pillow-name',
                    action='store',
                    dest='pillow_name',
                    default=None,
                    help="Run a single specific pillow name from settings.PILLOWTOPS list"),
    )

    def handle_noargs(self, **options):
        run_all = options['run_all']
        list_all = options['list_all']
        list_checkpoints = options['list_checkpoints']
        pillow_name = options['pillow_name']
        pillow_key = options['pillow_key']
        all_pillows = [pillow for group_key, items in settings.PILLOWTOPS.items() for pillow in items]

        if list_all:
            print "\nPillows registered in system:"
            for k,v in settings.PILLOWTOPS.items():
                print "\tKey: %s" % k
                for p in v:
                    print "\t\t%s" % p.split('.')[-1]
            print "\n\tRun with --pillow-name <name> to run a pillow"
            print "\n\tRun with --pillow-key <key> to run a group of pillows together (for local dev convenience purposes)\n"
            sys.exit()

        if run_all:
            pillows_to_run = all_pillows
        elif not run_all and not pillow_name and pillow_key:
            # get pillows from key

            if pillow_key not in settings.PILLOWTOPS:
                print "\n\tError, key %s is not in settings.PILLOWTOPS, legal keys are: %s" % \
                      (pillow_key, settings.PILLOWTOPS.keys())
                sys.exit()
            else:
                pillows_to_run = settings.PILLOWTOPS[pillow_key]

        elif not run_all and not pillow_key and pillow_name:
            abbreviated_pillows = [x.split('.')[-1] for x in all_pillows]
            if pillow_name not in abbreviated_pillows:
                print "\n\tError, key %s is not in settings.PILLOWTOPS, legal keys are: %s" % \
                      (pillow_name, settings.PILLOWTOPS.keys())
                sys.exit()
            else:
                pillow_idx = abbreviated_pillows.index(pillow_name)
                start_pillow(import_pillow_string(all_pillows[pillow_idx]))
            sys.exit()
        elif list_checkpoints:
            for pillow in get_all_pillows():
                print pillow.checkpoint_manager.checkpoint_id
            sys.exit()
        else:
            print "\nNo command set, please see --help for runtime instructions"
            sys.exit()

        start_pillows(pillows=[import_pillow_string(x) for x in pillows_to_run])
