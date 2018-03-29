from __future__ import absolute_import
from __future__ import print_function

from __future__ import unicode_literals
import gzip
import json
from datetime import datetime

from django.core.management.base import BaseCommand

from pillowtop import get_pillow_by_name, get_all_pillow_instances


class Command(BaseCommand):
    help = "Write remaining changes in queue for a pillow to file"

    def add_arguments(self, parser):
        parser.add_argument(
            '-p', '--pillow_class',
        )

    def handle(self, pillow_class=None, **options):
        if pillow_class:
            pillows = [get_pillow_by_name(pillow_class)]
        else:
            pillows = get_all_pillow_instances()

        for pillow in pillows:
            last_sequence = pillow.get_last_checkpoint_sequence()
            filepath = 'pillow_changes_{}_{}.gz'.format(
                pillow.get_name(), datetime.utcnow().replace(microsecond=0).isoformat()
            )
            filepath = filepath.replace(':', '')
            self.stdout.write("\n    Writing changes to {}\n\n".format(filepath))
            with gzip.open(filepath, 'wb') as file:
                for change in pillow.get_change_feed().iter_changes(since=last_sequence, forever=False):
                    if change:
                        doc = change.to_dict()
                        if change.metadata:
                            doc['metadata'] = change.metadata.to_json()
                        doc.pop('doc', None)
                        file.write('{}\n'.format(json.dumps(doc)))
