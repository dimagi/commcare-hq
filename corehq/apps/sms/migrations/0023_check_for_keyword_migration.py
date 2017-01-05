# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations
from corehq.sql_db.operations import HqRunPython
from corehq.apps.sms.migration_status import assert_keyword_migration_complete


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0022_keyword_last_modified'),
    ]

    operations = {
        HqRunPython(assert_keyword_migration_complete, reverse_code=noop),
    }
