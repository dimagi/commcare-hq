# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations



def copy_checkpoint(apps, schema_editor):
    DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
    try:
        checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id='default-couch-change-feed')
        # since checkpoint_id is the primary key, this should make a new model
        # which is good in case we need to rollback
        checkpoint.checkpoint_id = 'DefaultChangeFeedPillow'
        checkpoint.save()
    except DjangoPillowCheckpoint.DoesNotExist:
        pass


def delete_checkpoint(apps, schema_editor):
    DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
    try:
        checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id='DefaultChangeFeedPillow')
        checkpoint.delete()
    except DjangoPillowCheckpoint.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0009_convert_final_checkpoints_to_sql'),
        ('pillowtop', '0002_djangopillowcheckpoint_sequence_format'),
    ]

    operations = [
        migrations.RunPython(copy_checkpoint, delete_checkpoint)
    ]
