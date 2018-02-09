# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.apps.cleanup.pillow_migrations import migrate_kafka_checkpoints, revert_migrate_checkpoints
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0012_add_es_index_to_checkpoint_ids'),
    ]

    operations = [
        HqRunPython(migrate_kafka_checkpoints, revert_migrate_checkpoints)
    ]
