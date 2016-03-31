# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.doctypemigrations.djangomigrations import assert_initial_complete
from corehq.doctypemigrations.migrator_instances import apps_migration
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0006_domain_migration_20151118'),
    ]

    operations = [
        HqRunPython(assert_initial_complete(apps_migration))
    ]
