# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.blobs.migrate import assert_migration_complete
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0001_initial'),
    ]

    operations = [
       HqRunPython(*assert_migration_complete("saved_exports"))
    ]
