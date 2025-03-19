import json

from django.core.management.base import BaseCommand, CommandError

from pillowtop.utils import get_pillow_by_name

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint


def confirm(msg):
    user_input = input("{} Type ['y', 'yes'] to continue.\n".format(msg))
    if user_input not in ['y', 'yes']:
        print('abort')
        exit()


class Command(BaseCommand):
    """
    You must first stop the targeted pillow before running this command, and be
    sure to start the pillow again once complete. An example usage is:
    ``cchq --control <env> service pillowtop stop --only=<pillow_name>``
    ``cchq --control <env> django-manage fix_checkpoint_after_rewind <pillow_name>``
    ``cchq --control <env> service pillowtop start --only=<pillow_name>``
    """
    help = ("Update the sequence ID of a pillow that has been rewound due to a cloudant issue")

    def add_arguments(self, parser):
        parser.add_argument('pillow_name')
        parser.add_argument('--by-partition', action='store_true')

    def handle(self, pillow_name, **options):
        confirm("Are you sure you want to reset the checkpoint for the '{}' pillow?".format(pillow_name))
        confirm("Have you stopped the pillow?")

        by_partition = options['by_partition']
        pillow = get_pillow_by_name(pillow_name)
        if not pillow:
            raise CommandError("No pillow found with name: {}".format(pillow_name))

        checkpoint = pillow.checkpoint
        store = HistoricalPillowCheckpoint.get_historical_max(checkpoint.checkpoint_id, by_partition)

        if not store:
            print("No new sequence exists for that pillow. You'll have to do it manually.")
            exit()

        old_seq = pillow.get_last_checkpoint_sequence()
        if by_partition:
            # update_to expects a json string or a list of tuples
            new_seq = json.dumps(store)
        else:
            new_seq = store.seq
        confirm("\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(
            pillow_name, old_seq, new_seq
        ))
        checkpoint.update_to(new_seq)
        print("Checkpoint updated")
