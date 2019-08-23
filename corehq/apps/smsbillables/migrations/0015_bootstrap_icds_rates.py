# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_icds_gateway import bootstrap_icds_gateway



def create_icds_rates(apps, schema_editor):
    bootstrap_icds_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0014_bootstrap_apposit_rates'),
    ]

    operations = {
        migrations.RunPython(create_icds_rates),
    }
