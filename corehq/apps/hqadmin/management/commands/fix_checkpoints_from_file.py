import json

from django.core.management import BaseCommand, CommandError
from pillowtop import get_pillow_by_name
from six.moves import input
from io import open


class Command(BaseCommand):
    help = ("Update the pillow sequence IDs based on a passed in file")

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help="Disable interactive mode",
        )

    def handle(self, filename, **options):
        with open(filename, encoding='utf-8') as f:
            checkpoint_map = json.loads(f.read())

        for pillow_name in sorted(checkpoint_map.keys()):
            checkpoint_to_set = checkpoint_map[pillow_name]
            pillow = get_pillow_by_name(pillow_name)
            if not pillow:
                raise CommandError("No pillow found with name: {}".format(pillow_name))

            old_seq = pillow.get_checkpoint().wrapped_sequence
            msg = "\nReset checkpoint for '{}' pillow from:\n\n{}\n\nto\n\n{}\n\n".format(
                pillow_name, old_seq, checkpoint_to_set,
            )
            if not options['noinput'] and \
                    input("{} Type ['y', 'yes'] to continue.\n".format(msg)) not in ['y', 'yes']:
                print('skipped')
                continue
            pillow.checkpoint.update_to(checkpoint_to_set)
