# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.apps.accounting.bootstrap.config.user_buckets_jan_2017 import (
    BOOTSTRAP_CONFIG
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.sql_db.operations import HqRunPython


def _bootstrap_with_updated_user_buckets(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0048_remove_defaultproductplan_product_type'),
    ]

    operations = [
        HqRunPython(_bootstrap_with_updated_user_buckets),
    ]
