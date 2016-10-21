# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.cchq_software_plan_bootstrap import (
    BOOTSTRAP_EDITION_TO_ROLE,
    BOOTSTRAP_FEATURE_RATES,
    BOOTSTRAP_PRODUCT_RATES,
    FEATURE_TYPES,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.sql_db.operations import HqRunPython


def cchq_software_plan_bootstrap(apps, schema_editor):
    ensure_plans(
        edition_to_role=BOOTSTRAP_EDITION_TO_ROLE,
        edition_to_product_rate=BOOTSTRAP_PRODUCT_RATES,
        edition_to_feature_rate=BOOTSTRAP_FEATURE_RATES,
        feature_types=FEATURE_TYPES,
        dry_run=False, verbose=True, apps=apps,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_update_pricing_table'),
    ]

    operations = [
        HqRunPython(cchq_software_plan_bootstrap),
    ]
