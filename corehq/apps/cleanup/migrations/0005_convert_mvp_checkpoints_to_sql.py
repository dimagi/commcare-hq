# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0004_convert_ucr_checkpoints_to_sql'),
    ]

    operations = [
        noop_migration()
    ]
