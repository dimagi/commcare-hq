import json
from django.core.management import BaseCommand, CommandError
from corehq.apps.hqadmin.management.commands.fix_checkpoint_after_rewind import confirm, set_checkpoint
from pillowtop import get_pillow_by_name


class Command(BaseCommand):
    args = 'filename'
    help = ("Update the pillow sequence IDs based on a passed in file")

    def handle(self, filename, *args, **options):
        with open(filename) as f:
            checkpoint_map = json.loads(f.read())

        for pillow_name, checkpoint_to_set in checkpoint_map.items():
            pillow = get_pillow_by_name(pillow_name)
            if not pillow:
                raise CommandError("No pillow found with name: {}".format(pillow_name))

            old_seq = pillow.get_checkpoint()['seq']
            confirm("\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(
                pillow_name, old_seq, checkpoint_to_set
            ))
            set_checkpoint(pillow, checkpoint_to_set)
