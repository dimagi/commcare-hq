from __future__ import print_function

import difflib
import json
import pprint

from datetime import datetime

import argparse

import re
from django.core.management import BaseCommand, CommandError

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from pillowtop import get_pillow_by_name
from pillowtop.models import str_to_kafka_seq
from pillowtop.utils import get_all_pillow_instances


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def confirm(msg):
    input = raw_input("{} Type ['y', 'yes'] to continue.\n".format(msg))
    if input in ['y', 'yes']:
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
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help="Disable interactive mode",
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

            if not confirm('Update checkpoints for {}?'.format(', '.join(p.pillow_id for p in pillows))):
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

            if old_seq == new_seq:
                print('Sequences are identical, moving on.')
                continue

            if confirm("\nReset checkpoint for '{}' pillow:\n\n{}\n".format(
                    pillow.pillow_id, diff
            )):
                pillow.checkpoint.update_to(new_seq)
                print("Checkpoint for {} updated".format(pillow.pillow_id))
