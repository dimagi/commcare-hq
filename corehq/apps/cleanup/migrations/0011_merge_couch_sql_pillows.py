# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.apps.change_feed import topics
from corehq.apps.cleanup.pillow_migrations import merge_kafka_pillow_checkpoints, CheckpointTopic
from corehq.sql_db.operations import HqRunPython


def merge_checkpoints(new_checkpoint_id, checkpoint_topics):
    def _inner(apps, schema_editor):
        merge_kafka_pillow_checkpoints(new_checkpoint_id, checkpoint_topics, apps)
    return _inner


def delete_checkpoint(checkpoint_id):
    def _inner(apps, schema_editor):
        DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
        try:
            checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id=checkpoint_id)
            checkpoint.delete()
        except DjangoPillowCheckpoint.DoesNotExist:
            pass
    return _inner


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0010_rename_default_change_feed_checkpoint'),
    ]

    operations = [
        HqRunPython(
            merge_checkpoints(
                'all-cases-to-elasticsearch',
                [
                    CheckpointTopic('couch-cases-to-elasticsearch', topics.CASE),
                    CheckpointTopic('sql-cases-to-elasticsearch', topics.CASE_SQL)
                ]
            ),
            delete_checkpoint('all-cases-to-elasticsearch')
        ),
        HqRunPython(
            merge_checkpoints(
                'all-xforms-to-elasticsearch',
                [
                    CheckpointTopic('couch-xforms-to-elasticsearch', topics.FORM),
                    CheckpointTopic('sql-xforms-to-elasticsearch', topics.FORM_SQL)
                ]
            ),
            delete_checkpoint('all-xforms-to-elasticsearch')
        ),
    ]
