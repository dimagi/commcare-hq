# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import cchq_prbac_bootstrap
from corehq.sql_db.operations import HqRunPython


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0020_nonnullable_product_rate'),
    ]

    operations = [
        HqRunPython(cchq_prbac_bootstrap),
    ]
