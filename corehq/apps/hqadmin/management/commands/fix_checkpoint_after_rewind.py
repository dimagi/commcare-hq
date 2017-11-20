from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from pillowtop.utils import get_pillow_by_name
from six.moves import input


def confirm(msg):
    user_input = input("{} Type ['y', 'yes'] to continue.\n".format(msg))
    if user_input not in ['y', 'yes']:
        print('abort')
        exit()


class Command(BaseCommand):
    help = ("Update the sequence ID of a pillow that has been rewound due to a cloudant issue")

    def add_arguments(self, parser):
        parser.add_argument('pillow_name')

    def handle(self, pillow_name, **options):
        confirm("Are you sure you want to reset the checkpoint for the '{}' pillow?".format(pillow_name))
        confirm("Have you stopped the pillow?")

        pillow = get_pillow_by_name(pillow_name)
        if not pillow:
            raise CommandError("No pillow found with name: {}".format(pillow_name))

        checkpoint = pillow.checkpoint
        store = HistoricalPillowCheckpoint.get_historical_max(checkpoint.checkpoint_id)

        if not store:
            print("No new sequence exists for that pillow. You'll have to do it manually.")
            exit()

        old_seq = pillow.get_last_checkpoint_sequence()
        new_seq = store.seq
        confirm("\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(
            pillow_name, old_seq, new_seq
        ))
        checkpoint.update_to(new_seq)
        print("Checkpoint updated")
