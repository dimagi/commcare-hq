# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from sqlalchemy import Table, MetaData
from corehq.sql_db.connections import connection_manager
from corehq.sql_db.operations import HqRunPython
from corehq.util.decorators import change_log_level
from django.db import migrations


@change_log_level('sqlalchemy.engine', logging.INFO)  # show SQL commands
def drop_tables(apps, schema_editor):
    metadata = MetaData(bind=connection_manager.get_engine())

    for table_name in [
        'fluff_OPMHierarchyFluff',
        'fluff_OpmCaseFluff',
        'fluff_OpmFormFluff',
        'fluff_OpmHealthStatusAllInfoFluff',
        'fluff_VhndAvailabilityFluff',
    ]:
        Table(table_name, metadata).drop(checkfirst=True)


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        HqRunPython(drop_tables),
    ]
