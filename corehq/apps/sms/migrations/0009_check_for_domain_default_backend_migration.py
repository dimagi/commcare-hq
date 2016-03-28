# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations
from corehq.sql_db.operations import HqRunPython
from corehq.apps.sms.migration_status import assert_domain_default_backend_migration_complete


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0008_add_backend_mapping_unique_constraint'),
    ]

    operations = {
        HqRunPython(assert_domain_default_backend_migration_complete, reverse_code=noop),
    }
