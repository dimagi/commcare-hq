# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.apps.cleanup.pillow_migrations import migrate_legacy_pillows, noop_reverse_migration
from corehq.sql_db.operations import HqRunPython


def migrate_pillows(apps, schema_editor):
    pillow_names = [
        'UnknownUsersPillow',
        'GroupToUserPillow',
    ]
    migrate_legacy_pillows(apps, pillow_names)


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0008_convert_sofabed_checkpoints_to_sql'),
    ]

    operations = [
        HqRunPython(migrate_pillows, noop_reverse_migration)
    ]
