# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.resellers_and_managed_hosting import (
    BOOTSTRAP_CONFIG
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.sql_db.operations import HqRunPython


def cchq_new_editions_bootstrap(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0027_auto_20160422_1744'),
    ]

    operations = [
        HqRunPython(cchq_new_editions_bootstrap),
    ]
