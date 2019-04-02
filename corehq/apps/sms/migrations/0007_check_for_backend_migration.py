# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import
from django.db import migrations

from corehq.apps.sms.migration_status import assert_backend_migration_complete


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0006_add_migrationstatus'),
    ]

    operations = {
        migrations.RunPython(assert_backend_migration_complete, reverse_code=noop),
    }
