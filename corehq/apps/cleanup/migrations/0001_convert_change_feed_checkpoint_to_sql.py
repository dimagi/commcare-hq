# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.apps.cleanup.pillow_migrations import noop_reverse_migration, migrate_legacy_pillow_by_name
from corehq.sql_db.operations import HqRunPython


def migrate_pillow(apps, schema_editor):
    migrate_legacy_pillow_by_name(apps, 'DefaultChangeFeedPillow')


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0001_initial'),
    ]

    operations = [
        HqRunPython(migrate_pillow, noop_reverse_migration)
    ]
