# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import
from django.db import migrations

from corehq.apps.sms.migration_status import assert_domain_default_backend_migration_complete


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0008_add_backend_mapping_unique_constraint'),
    ]

    operations = {
        migrations.RunPython(assert_domain_default_backend_migration_complete, reverse_code=noop),
    }
