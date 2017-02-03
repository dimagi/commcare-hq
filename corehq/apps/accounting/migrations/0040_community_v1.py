# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.community_v1 import BOOTSTRAP_CONFIG
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap
from corehq.sql_db.operations import HqRunPython


def _bootstrap_new_community_role(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0039_auto_20160829_0828'),
    ]

    operations = [
        HqRunPython(cchq_prbac_bootstrap),
        HqRunPython(_bootstrap_new_community_role),
    ]
