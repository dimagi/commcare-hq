# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.management.commands.cchq_software_plan_bootstrap import ensure_plans
from corehq.sql_db.operations import HqRunPython


def cchq_software_plan_bootstrap(apps, schema_editor):
    ensure_plans(dry_run=False, verbose=True, for_tests=False, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_update_pricing_table'),
    ]

    operations = [
        HqRunPython(cchq_software_plan_bootstrap),
    ]
