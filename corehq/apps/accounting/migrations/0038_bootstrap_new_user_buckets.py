# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.new_user_numbers import (
    BOOTSTRAP_CONFIG
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.sql_db.operations import HqRunPython


def _bootstrap_new_community_plan_versions(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, dry_run=False, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0037_assign_explicit_community_subscriptions'),
    ]

    operations = [
        HqRunPython(_bootstrap_new_community_plan_versions),
    ]
