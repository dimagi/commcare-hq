import json
from django.core.management import BaseCommand, CommandError
from pillowtop import get_pillow_by_name


class Command(BaseCommand):
    args = 'filename'
    help = ("Update the pillow sequence IDs based on a passed in file")

    def handle(self, filename, *args, **options):
        with open(filename) as f:
            checkpoint_map = json.loads(f.read())

        for pillow_name in sorted(checkpoint_map.keys()):
            checkpoint_to_set = checkpoint_map[pillow_name]
            pillow = get_pillow_by_name(pillow_name)
            if not pillow:
                raise CommandError("No pillow found with name: {}".format(pillow_name))

            old_seq = pillow.get_checkpoint()['seq']
            msg = "\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(
                pillow_name, old_seq, checkpoint_to_set,
            )
            input = raw_input("{} Type ['y', 'yes'] to continue.\n".format(msg))
            if input not in ['y', 'yes']:
                print 'skipped'
                continue
            pillow.checkpoint.update_to(checkpoint_to_set)
