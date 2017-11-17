# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models

from corehq.blobs.migrate import assert_migration_complete
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0002_auto_20151221_1623'),
    ]

    operations = [
        HqRunPython(*assert_migration_complete("applications")),
        HqRunPython(*assert_migration_complete("multimedia")),
        HqRunPython(*assert_migration_complete("xforms")),
    ]
