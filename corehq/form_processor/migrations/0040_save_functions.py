# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0039_case_functions'),
    ]

    operations = [
        noop_migration()
    ]
