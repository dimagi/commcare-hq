# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.report_builder_v0 import BOOTSTRAP_CONFIG
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap
from corehq.sql_db.operations import HqRunPython


def bootstrap_report_builder_plans(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0051_add_report_builder_flag'),
    ]

    operations = [
        HqRunPython(cchq_prbac_bootstrap),
        HqRunPython(bootstrap_report_builder_plans),
    ]
