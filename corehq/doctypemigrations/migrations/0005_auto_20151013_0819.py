# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.doctypemigrations.djangomigrations import assert_initial_complete
from corehq.doctypemigrations.migrator_instances import fixtures_migration
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0004_auto_20151001_1809'),
    ]

    operations = {
        HqRunPython(assert_initial_complete(fixtures_migration))
    }
