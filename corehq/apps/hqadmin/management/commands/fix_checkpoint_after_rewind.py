from django.core.management.base import BaseCommand, CommandError
from corehq.apps.hqadmin.models import PillowCheckpointSeqStore
from pillowtop.utils import get_pillow_by_name


def confirm(msg):
    input = raw_input("{} Type ['y', 'yes'] to continue.\n".format(msg))
    if input not in ['y', 'yes']:
        print 'abort'
        exit()


class Command(BaseCommand):
    args = 'pillow_name'
    help = ("Update the sequence ID of a pillow that has been rewound due to a cloudant issue")

    def handle(self, *args, **options):
        pillow_name = args[0]

        confirm("Are you sure you want to reset the checkpoint for the '{}' pillow?".format(pillow_name))
        confirm("Have you stopped the pillow?")

        pillow = get_pillow_by_name(pillow_name)
        if not pillow:
            raise CommandError("No pillow found with name: {}".format(pillow_name))

        checkpoint = pillow.get_checkpoint()
        try:
            seq = PillowCheckpointSeqStore.objects.get(checkpoint_id=checkpoint.checkpoint_id)
        except PillowCheckpointSeqStore.DoesNotExist:
            print "No new sequence exists for that pillow. You'll have to do it manually."
            exit()

        old_seq = checkpoint.sequence
        new_seq = seq.seq
        confirm("\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(pillow_name, old_seq, new_seq))
        pillow.checkpoint.update_to(new_seq)
        print "Checkpoint updated"
