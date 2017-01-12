# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.cchq_software_plan_bootstrap import (
    BOOTSTRAP_CONFIG as ORIGINAL_BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.config.community_v1 import (
    BOOTSTRAP_CONFIG as COMMUNITY_V1_BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.config.resellers_and_managed_hosting import (
    BOOTSTRAP_CONFIG as RESELLERS_BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.sql_db.operations import HqRunPython


# from 0003_bootstrap
def cchq_software_plan_bootstrap(apps, schema_editor):
    ensure_plans(ORIGINAL_BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


# from 0028_bootstrap_new_editions
def cchq_new_editions_bootstrap(apps, schema_editor):
    ensure_plans(RESELLERS_BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps) #


# from 0040_community_v1
def _bootstrap_new_community_role(apps, schema_editor):
    ensure_plans(COMMUNITY_V1_BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0046_created_by_blank'),
    ]

    operations = [
        HqRunPython(cchq_software_plan_bootstrap),
        HqRunPython(cchq_new_editions_bootstrap),
        HqRunPython(_bootstrap_new_community_role),
    ]
