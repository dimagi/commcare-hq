# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import migrate_legacy_pillows, noop_reverse_migration


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
        migrations.RunPython(migrate_pillows, noop_reverse_migration)
    ]
