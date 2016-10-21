# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.apps.accounting.bootstrap.config.community_v1 import (
    BOOTSTRAP_EDITION_TO_ROLE,
    BOOTSTRAP_FEATURE_RATES,
    BOOTSTRAP_PRODUCT_RATES,
    FEATURE_TYPES,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap
from corehq.sql_db.operations import HqRunPython


def _bootstrap_new_community_role(apps, schema_editor):
    ensure_plans(
        edition_to_role=BOOTSTRAP_EDITION_TO_ROLE,
        edition_to_product_rate=BOOTSTRAP_PRODUCT_RATES,
        edition_to_feature_rate=BOOTSTRAP_FEATURE_RATES,
        feature_types=FEATURE_TYPES,
        dry_run=False, verbose=True, apps=apps,
    )

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0039_auto_20160829_0828'),
    ]

    operations = [
        HqRunPython(cchq_prbac_bootstrap),
        HqRunPython(_bootstrap_new_community_role),
    ]
