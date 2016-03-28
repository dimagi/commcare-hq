from pillowtop.run_pillowtop import start_pillows, start_pillow

from optparse import make_option
import sys
from django.conf import settings
from pillowtop.utils import get_all_pillow_instances, get_all_pillow_configs, \
    get_pillow_config_from_setting, get_pillow_by_name
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
        if list_all:
            print "\nPillows registered in system:"
            for config in get_all_pillow_configs():
                print u'{}: {}'.format(config.section, config.name)

            print "\n\tRun with --pillow-name <name> to run a pillow"
            print "\n\tRun with --pillow-key <key> to run a group of pillows together\n"
            sys.exit()

        if run_all:
            pillows_to_run = get_all_pillow_configs()
        elif not run_all and not pillow_name and pillow_key:
            # get pillows from key
            if pillow_key not in settings.PILLOWTOPS:
                print "\n\tError, key %s is not in settings.PILLOWTOPS, legal keys are: %s" % \
                      (pillow_key, settings.PILLOWTOPS.keys())
                sys.exit()
            else:
                pillows_to_run = [get_pillow_config_from_setting(pillow_key, config)
                                  for config in settings.PILLOWTOPS[pillow_key]]

        elif not run_all and not pillow_key and pillow_name:
            pillow = get_pillow_by_name(pillow_name)
            start_pillow(pillow)
            sys.exit()
        elif list_checkpoints:
            for pillow in get_all_pillow_instances():
                print pillow.checkpoint.checkpoint_id
            sys.exit()
        else:
            print "\nNo command set, please see --help for runtime instructions"
            sys.exit()

        start_pillows(pillows=[pillow_config.get_instance() for pillow_config in pillows_to_run])
