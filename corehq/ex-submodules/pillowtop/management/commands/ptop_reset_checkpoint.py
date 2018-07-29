from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
import sys
from pillowtop import get_pillow_by_name, get_all_pillow_configs
from six.moves import input


class Command(BaseCommand):
    help = "Reset checkpoints for pillowtop"

    def add_arguments(self, parser):
        parser.add_argument(
            'pillow_class',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='interactive',
            default=False,
            help="Suppress confirmation messages - dangerous mode!",
        )

    def handle(self, pillow_class, **options):
        """
        More targeted pillow checkpoint reset system - must specify the pillow class_name to reset the checkpoint
        """

        pillow_to_use = get_pillow_by_name(pillow_class)
        if not pillow_to_use:
            print("")
            print("\n\tPillow class [%s] not in configuration, what are you trying to do?\n" % pillow_class)
            sys.exit()

        if not options.get('interactive'):
            confirm = input("""
            You have requested to reset the checkpoints for the pillow [%s]. This is an irreversible
            operation, and may take a long time, and cause extraneous updates to the requisite
            consumers of the _changes feeds  Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % pillow_class)
        else:
            confirm = 'yes'

        if confirm != 'yes':
            print("Reset cancelled.")
            return

        print("Resetting checkpoint for %s" % pillow_to_use.checkpoint.checkpoint_id)
        print("\tOld checkpoint: %s" % pillow_to_use.get_checkpoint().wrapped_sequence)
        pillow_to_use.checkpoint.reset()
        print("\n\tNew checkpoint reset to zero")
