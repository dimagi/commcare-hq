from casexml.apps.case.models import CommCareCase
import logging
from pillowtop.checkpoints.util import construct_checkpoint_doc_id_from_name
from pillowtop.utils import get_pillow_config_by_name


def noop_reverse_migration(apps, schema_editor):
    # by default the reverse migration does nothing
    pass


def migrate_legacy_pillows(migration_apps, pillow_names):
    for pillow_name in pillow_names:
        migrate_legacy_pillow_by_name(migration_apps, pillow_name)


def migrate_legacy_pillow_by_name(migration_apps, pillow_name):
    try:
        DjangoPillowCheckpoint = migration_apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
        pillow_config = get_pillow_config_by_name(pillow_name)
        checkpoint_id = construct_checkpoint_doc_id_from_name(pillow_config.get_class().get_legacy_name())
        legacy_checkpoint = CommCareCase.get_db().get(checkpoint_id)
        new_checkpoint = DjangoPillowCheckpoint(
            checkpoint_id=pillow_config.get_instance().checkpoint.checkpoint_id,
            sequence=legacy_checkpoint['seq'],
            old_sequence=legacy_checkpoint.get('old_seq', None)
        )
        new_checkpoint.save()
    except Exception as e:
        logging.exception('Failed to update pillow checkpoint. {}'.format(e))
