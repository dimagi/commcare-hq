# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from sqlalchemy import Table, MetaData
from corehq.db import connection_manager
from django.db import migrations


def drop_tables(apps, schema_editor):
    # show SQL commands
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    metadata = MetaData(bind=connection_manager.get_engine())

    for table_name in [
        'fluff_OPMHierarchyFluff',
        'fluff_OpmCaseFluff',
        'fluff_OpmFormFluff',
        'fluff_OpmHealthStatusAllInfoFluff',
        'fluff_VhndAvailabilityFluff',
    ]:
        Table(table_name, metadata).drop()


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunPython(drop_tables),
    ]
