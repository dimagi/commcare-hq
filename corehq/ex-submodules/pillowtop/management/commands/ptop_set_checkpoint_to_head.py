from __future__ import print_function
from django.core.management.base import BaseCommand, LabelCommand
import sys
from pillowtop import get_pillow_by_name, get_all_pillow_configs


class Command(LabelCommand):
    help = "Set checkpoints for pillowtop to HEAD of change feed."
    args = "[pillow_name]"
    label = "Pillow Name"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='interactive',
            default=False,
            help="Suppress confirmation messages - dangerous mode!",
        )

    def handle_label(self, pillow_name, **options):
        """
        More targeted pillow checkpoint reset system - must specify the pillow class_name to reset the checkpoint
        """
        pillow_to_use = get_pillow_by_name(pillow_name)
        if not pillow_to_use:
            print("")
            print("\n\tPillow class [%s] not in configuration, what are you trying to do?\n" % pillow_name)
            return

        checkpoint_head = pillow_to_use.get_change_feed().get_checkpoint_value()
        print("\nSetting checkpoint for %s" % pillow_to_use.checkpoint.checkpoint_id)
        print("\tOld checkpoint: %s" % pillow_to_use.get_checkpoint().sequence)
        print("\tNew checkpoint: %s" % checkpoint_head)

        if not options.get('interactive'):
            confirm = raw_input("""
            Confirm you want to do this? This will fast forward the pillow "%s" to the HEAD of
            the change feed and may skip out changes that have not been processed.

            Type 'yes' to continue, or 'no' to cancel: """ % pillow_name)
        else:
            confirm = 'yes'

        if confirm != 'yes':
            print("Cancelled.")
            return

        pillow_to_use.checkpoint.update_to(checkpoint_head)
