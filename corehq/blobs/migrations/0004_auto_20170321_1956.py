# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.blobs.migrate import assert_migration_complete
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0003_auto_20161012_1358'),
    ]

    operations = [
        HqRunPython(*assert_migration_complete("cases")),
    ]
