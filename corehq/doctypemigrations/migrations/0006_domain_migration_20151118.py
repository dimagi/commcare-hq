# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.doctypemigrations.djangomigrations import assert_initial_complete
from corehq.doctypemigrations.migrator_instances import domains_migration
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0005_auto_20151013_0819'),
    ]

    operations = {
        HqRunPython(assert_initial_complete(domains_migration))
    }
