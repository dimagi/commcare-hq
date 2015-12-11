# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.management import call_command
from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def cchq_software_plan_bootstrap(*args):
    call_command('cchq_software_plan_bootstrap')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_update_pricing_table'),
    ]

    operations = [
        HqRunPython(cchq_software_plan_bootstrap),
    ]
