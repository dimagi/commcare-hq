from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.run_pillowtop import start_pillows, start_pillow
from pillowtop.utils import (
    get_all_pillow_instances,
    get_all_pillow_configs,
    get_pillow_config_from_setting,
    get_pillow_by_name
)


class Command(BaseCommand):
    help = "Run pillows pillows listed in settings."

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            dest='run_all',
            default=False,
            help="Run all pillows from settings - use for local dev",
        )
        parser.add_argument(
            '--list',
            action='store_true',
            dest='list_all',
            default=False,
            help="List pillowtop names",
        )
        parser.add_argument(
            '--list-checkpoints',
            action='store_true',
            dest='list_checkpoints',
            default=False,
            help="Print all pillow doc ids.",
        )
        parser.add_argument(
            '--pillow-key',
            action='store',
            dest='pillow_key',
            default=None,
            help="Run a specific key of a group of pillows from settings.PILLOWTOPS list",
        )
        parser.add_argument(
            '--pillow-name',
            action='store',
            dest='pillow_name',
            default=None,
            help="Run a single specific pillow name from settings.PILLOWTOPS list",
        )
        parser.add_argument(
            '--num-processes',
            action='store',
            dest='num_processes',
            default=1,
            type=int,
            help="The number of processes that are expected to be run for this pillow",
        )
        parser.add_argument(
            '--process-number',
            action='store',
            dest='process_number',
            default=0,
            type=int,
            help="The process number of this pillow process. Should be between 0 and num-processes. "
                 "It's expected that there will only be one process for each number running at once",
        )
        parser.add_argument(
            '--processor-chunk-size',
            action='store',
            dest='processor_chunk_size',
            default=DEFAULT_PROCESSOR_CHUNK_SIZE,
            type=int,
            help="The process number of this pillow process. Should be between 0 and num-processes. "
                 "It's expected that there will only be one process for each number running at once",
        )

    def handle(self, **options):
        run_all = options['run_all']
        list_all = options['list_all']
        list_checkpoints = options['list_checkpoints']
        pillow_name = options['pillow_name']
        pillow_key = options['pillow_key']
        num_processes = options['num_processes']
        process_number = options['process_number']
        processor_chunk_size = options['processor_chunk_size']
        assert 0 <= process_number < num_processes
        assert processor_chunk_size
        if list_all:
            print("\nPillows registered in system:")
            for config in get_all_pillow_configs():
                print('{}: {}'.format(config.section, config.name))

            print("\n\tRun with --pillow-name <name> to run a pillow")
            print("\n\tRun with --pillow-key <key> to run a group of pillows together\n")
            sys.exit()

        if run_all:
            pillows_to_run = get_all_pillow_configs()
        elif not run_all and not pillow_name and pillow_key:
            # get pillows from key
            if pillow_key not in settings.PILLOWTOPS:
                print("\n\tError, key %s is not in settings.PILLOWTOPS, legal keys are: %s" % \
                      (pillow_key, list(settings.PILLOWTOPS)))
                sys.exit()
            else:
                pillows_to_run = [get_pillow_config_from_setting(pillow_key, config)
                                  for config in settings.PILLOWTOPS[pillow_key]]

        elif not run_all and not pillow_key and pillow_name:
            pillow = get_pillow_by_name(pillow_name, num_processes=num_processes, process_num=process_number, processor_chunk_size=processor_chunk_size)
            start_pillow(pillow)
            sys.exit()
        elif list_checkpoints:
            for pillow in get_all_pillow_instances():
                print(pillow.checkpoint.checkpoint_id)
            sys.exit()
        else:
            print("\nNo command set, please see --help for runtime instructions")
            sys.exit()

        start_pillows(pillows=[pillow_config.get_instance() for pillow_config in pillows_to_run])
