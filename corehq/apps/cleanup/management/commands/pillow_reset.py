import json
from datetime import datetime
from couchdbkit import ResourceNotFound
from django.core.management.base import LabelCommand, CommandError
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import json_format_datetime
from pillowtop.utils import import_pillow_string


class Command(LabelCommand):
    help = "Reset a list of pillow checkpoints based on a specified config file."
    args = "config_file"
    label = "config file"

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Usage is ./manage.py pillow_reset [config_file]!")

        file_path = args[0]
        db = get_db()
        checkpoints = []
        with open(file_path) as f:
            config = PillowResetConfig.wrap(json.loads(f.read()))
            for pillow in config.pillows:
                checkpoint_doc_name = pillow.checkpoint_manager.checkpoint_id
                try:
                    checkpoint_doc = db.get(checkpoint_doc_name)
                except ResourceNotFound:
                    print 'ERROR - checkpoint {} not found!'.format(checkpoint_doc_name)
                    continue

                def _fmt(seq_id):
                    if isinstance(seq_id, basestring) and len(seq_id) > 20:
                        return '{}...'.format(seq_id[:20])
                    else:
                        return seq_id

                print 'resetting {} from {} to {}...'.format(
                    checkpoint_doc_name,
                    _fmt(checkpoint_doc['seq']),
                    _fmt(config.seq),
                )
                # add metadata properties in case we need to revert this for any reason
                checkpoint_doc['reset_from'] = checkpoint_doc['seq']
                checkpoint_doc['reset_on'] = json_format_datetime(datetime.utcnow())
                checkpoint_doc['seq'] = config.seq
                checkpoints.append(checkpoint_doc)

        if raw_input('Commit the above resets to the database? (y/n) \n').lower() == 'y':
            db.bulk_save(checkpoints)
        else:
            print 'pillow checkpoints not saved.'


class PillowResetConfig(JsonObject):
    seq = StringProperty(required=True)
    pillow_names = ListProperty(required=True)

    @property
    def pillows(self):
        return [import_pillow_string(name) for name in self.pillow_names]
