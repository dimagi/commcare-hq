
import argparse
import difflib
import pprint
import re
from datetime import datetime

from django.core.management import BaseCommand, CommandError

from six.moves import input

from pillowtop.models import str_to_kafka_seq
from pillowtop.utils import get_all_pillow_instances

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def confirm(msg):
    user_input = input("{} Type ['y', 'yes'] to continue.\n".format(msg))
    if user_input in ['y', 'yes']:
        return True


class Command(BaseCommand):
    help = ("Update the pillow sequence IDs based on a passed in file")

    def add_arguments(self, parser):
        parser.add_argument(
            'date',
            type=valid_date,
            help="Take first checkpoint before date - format = YYYY-MM-DD",
        )
        parser.add_argument(
            '--pillows',
            nargs='+',
            help="Restrict changes to only these pillows. (regex supported)"
        )

    def handle(self, **options):
        date = options['date']
        pillow_args = set(options['pillows'] or [])

        if not pillow_args and not confirm('Reset checkpoints ALL pillows?'):
            raise CommandError('Abort')

        def _pillow_match(pillow_id):
            return (
                pillow_id in pillow_args
                or any(re.match(arg, pillow_id, re.IGNORECASE) for arg in pillow_args)
            )

        all_pillows = get_all_pillow_instances()
        if not pillow_args:
            pillows = all_pillows
        else:
            pillows = [
                pillow for pillow in all_pillows
                if _pillow_match(pillow.pillow_id)
            ]

            if not pillows:
                raise CommandError('No pillows match: {}'.format(options['pillows']))

            if not confirm('Update checkpoints for {}?'.format('\n  '.join(p.pillow_id for p in pillows))):
                raise CommandError('abort')

        for pillow in pillows:
            checkpoint = pillow.checkpoint
            historical_checkpoint = HistoricalPillowCheckpoint.objects.filter(
                checkpoint_id=checkpoint.checkpoint_id,
                date_updated__lt=date).first()

            if not historical_checkpoint:
                print(self.style.ERROR('No historical checkpoints for {} before {}'.format(
                    checkpoint.checkpoint_id, date))
                )
                continue

            old_seq = pillow.get_last_checkpoint_sequence()
            new_seq = historical_checkpoint.seq
            if checkpoint.sequence_format == 'json' and isinstance(old_seq, dict):
                new_seq = str_to_kafka_seq(new_seq)
                diff = ('\n'.join(difflib.ndiff(
                    pprint.pformat(old_seq).splitlines(),
                    pprint.pformat(new_seq).splitlines())))
            else:
                diff = 'from: {}\nto  : {}'.format(old_seq, new_seq)

            pillow_id = pillow.pillow_id
            if old_seq == new_seq:
                print('Sequences for {} are identical, moving on.'.format(pillow_id))
                continue

            if confirm("\nReset checkpoint for '{}' pillow to sequence from  {}:\n\n{}\n".format(
                    pillow_id, historical_checkpoint.date_updated, diff
            )):
                pillow.checkpoint.update_to(new_seq)
                print(self.style.SUCCESS("Checkpoint for {} updated\n".format(pillow_id)))
