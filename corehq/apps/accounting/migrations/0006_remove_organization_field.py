# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def check_no_organizations(apps, schema_editor):
    if apps.get_model('accounting', 'Subscriber').objects.exclude(organization=None):
        raise Exception('There exists a Subscriber with an organization')


def empty_func(*args):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0005_merge'),
    ]

    operations = [
        HqRunPython(check_no_organizations, reverse_code=empty_func),
        migrations.RemoveField(
            model_name='subscriber',
            name='organization',
        ),
    ]
