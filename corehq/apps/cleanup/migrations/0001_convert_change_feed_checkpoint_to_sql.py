# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import logging
from casexml.apps.case.models import CommCareCase
from pillowtop.checkpoints.util import construct_checkpoint_doc_id_from_name
from pillowtop.utils import get_pillow_class, get_pillow_config_by_name


def migrate_pillow(apps, schema_editor):
    # todo: figure out how to generalize this.
    try:
        DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
        pillow_config = get_pillow_config_by_name('DefaultChangeFeedPillow')
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


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_pillow, reverse_migration)
    ]
