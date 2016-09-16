# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from django.core.management import call_command
from corehq.sql_db.operations import HqRunPython
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT


def _grandfather_exports(apps, schema_editor):
    call_command(
        'cchq_prbac_grandfather_privs',
        EXCEL_DASHBOARD,
        skip='community_plan_v1',
        noinput=True,
    )
    call_command(
        'cchq_prbac_grandfather_privs',
        DAILY_SAVED_EXPORT,
        skip='community_plan_v1',
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0039_auto_20160829_0828'),
    ]

    operations = [
        HqRunPython(_grandfather_exports),
    ]
