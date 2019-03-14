from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
from datetime import datetime
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import json_format_datetime
from pillowtop.utils import get_pillow_by_name
import six
from six.moves import input
from io import open

from corehq.util.python_compatibility import soft_assert_type_text


class Command(BaseCommand):
    help = "Reset a list of pillow checkpoints based on a specified config file."

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
        )

    def handle(self, file_path, **options):
        db = get_db()
        checkpoints = []
        with open(file_path, encoding='utf-8') as f:
            config = PillowResetConfig.wrap(json.loads(f.read()))
            for pillow in config.pillows:
                checkpoint_doc_name = pillow.checkpoint.checkpoint_id
                try:
                    checkpoint_doc = db.get(checkpoint_doc_name)
                except ResourceNotFound:
                    print('ERROR - checkpoint {} not found!'.format(checkpoint_doc_name))
                    continue

                def _fmt(seq_id):
                    if isinstance(seq_id, six.string_types) and len(seq_id) > 20:
                        soft_assert_type_text(seq_id)
                        return '{}...'.format(seq_id[:20])
                    else:
                        return seq_id

                print('resetting {} from {} to {}...'.format(
                    checkpoint_doc_name,
                    _fmt(checkpoint_doc['seq']),
                    _fmt(config.seq),
                ))
                # add metadata properties in case we need to revert this for any reason
                checkpoint_doc['reset_from'] = checkpoint_doc['seq']
                checkpoint_doc['reset_on'] = json_format_datetime(datetime.utcnow())
                checkpoint_doc['seq'] = config.seq
                checkpoints.append(checkpoint_doc)

        if input('Commit the above resets to the database? (y/n) \n').lower() == 'y':
            db.bulk_save(checkpoints)
        else:
            print('pillow checkpoints not saved.')


class PillowResetConfig(JsonObject):
    seq = StringProperty(required=True)
    pillow_names = ListProperty(required=True)

    @property
    def pillows(self):
        return [get_pillow_by_name(name) for name in self.pillow_names]
