# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0006_fix_functions'),
    ]

    operations = [
        noop_migration(),
    ]
