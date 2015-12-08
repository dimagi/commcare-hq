# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import migrate_legacy_pillows, noop_reverse_migration


def migrate_sofabed_pillows(apps, schema_editor):
    pillow_names = [
        'CaseDataPillow',
        'FormDataPillow',
    ]
    migrate_legacy_pillows(apps, pillow_names)


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0007_convert_es_checkpoints_to_sql'),
    ]

    operations = [
        migrations.RunPython(migrate_sofabed_pillows, noop_reverse_migration)
    ]
