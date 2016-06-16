# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

# code
from corehq.apps.accounting.management.commands.cchq_software_plan_bootstrap import ensure_plans
# data
from corehq.apps.accounting.management.commands.cchq_software_plan_bootstrap import (
    BOOTSTRAP_EDITION_TO_ROLE,
    BOOTSTRAP_FEATURE_RATES,
    BOOTSTRAP_PRODUCT_RATES,
    EDITIONS,
    FEATURE_TYPES,
    PRODUCT_TYPES,
)

from corehq.sql_db.operations import HqRunPython


def cchq_software_plan_bootstrap(apps, schema_editor):
    ensure_plans(
        editions=EDITIONS, edition_to_role=BOOTSTRAP_EDITION_TO_ROLE,
        product_types=PRODUCT_TYPES, product_rate_data=BOOTSTRAP_PRODUCT_RATES,
        feature_types=FEATURE_TYPES, feature_type_data=BOOTSTRAP_FEATURE_RATES,
        dry_run=False, verbose=True, for_tests=False, apps=apps,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_update_pricing_table'),
    ]

    operations = [
        HqRunPython(cchq_software_plan_bootstrap),
    ]
