# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import migrate_legacy_pillow_by_name, noop_reverse_migration
from corehq.sql_db.operations import HqRunPython


def migrate_mc_pillow(apps, schema_editor):
    migrate_legacy_pillow_by_name(apps, 'MalariaConsortiumFluffPillow')


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0001_convert_change_feed_checkpoint_to_sql'),
    ]

    operations = [
        HqRunPython(migrate_mc_pillow, noop_reverse_migration)
    ]
