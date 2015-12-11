# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_smsgh_gateway import \
    bootstrap_smsgh_gateway
from corehq.sql_db.operations import HqRunPython


def create_smsgh_rates(apps, schema_editor):
    bootstrap_smsgh_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0003_update_twilio_rates_outgoing'),
    ]

    operations = {
        HqRunPython(create_smsgh_rates),
    }
