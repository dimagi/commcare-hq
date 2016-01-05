# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations
from corehq.sql_db.operations import HqRunPython
from corehq.apps.sms.migration_status import assert_backend_migration_complete


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0006_add_migrationstatus'),
    ]

    operations = {
        HqRunPython(assert_backend_migration_complete, reverse_code=noop),
    }
