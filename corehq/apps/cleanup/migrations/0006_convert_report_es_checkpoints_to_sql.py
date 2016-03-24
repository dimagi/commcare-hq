# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import noop_reverse_migration, migrate_legacy_pillows
from corehq.sql_db.operations import HqRunPython


def migrate_report_es_pillows(apps, schema_editor):
    pillow_names = [
        "ReportCasePillow",
        "ReportXFormPillow",
    ]
    migrate_legacy_pillows(apps, pillow_names)


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0005_convert_mvp_checkpoints_to_sql'),
    ]

    operations = [
        HqRunPython(migrate_report_es_pillows, noop_reverse_migration)
    ]
