# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.management.commands.cchq_accounting_bootstrap_new_editions_042016 import ensure_plans
from corehq.sql_db.operations import HqRunPython


def cchq_new_editions_bootstrap(apps, schema_editor):
    ensure_plans(dry_run=False, verbose=True, for_tests=False, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0027_auto_20160422_1744'),
    ]

    operations = [
        HqRunPython(cchq_new_editions_bootstrap),
    ]
