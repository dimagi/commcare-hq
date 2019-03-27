# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_apposit_gateway import bootstrap_apposit_gateway



def create_apposit_rates(apps, schema_editor):
    bootstrap_apposit_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0013_auto_20160826_1531'),
    ]

    operations = {
        migrations.RunPython(create_apposit_rates),
    }
