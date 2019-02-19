# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import print_function

from django.core.management import call_command
from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def _migrate_roles_permissions(apps, schema_editor):
    call_command('migrate_roles_permissions_feb2019', noinput=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_domainrequest'),
    ]

    operations = [
        HqRunPython(_migrate_roles_permissions)
    ]
