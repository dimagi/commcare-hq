# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_twilio_gateway import \
    bootstrap_twilio_gateway
from corehq.sql_db.operations import HqRunPython


def update_twilio_rates_outgoing(apps, schema_editor):
    bootstrap_twilio_gateway(
        apps,
        'corehq/apps/smsbillables/management/commands/pricing_data/twilio-rates-2015_10_06.csv'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0002_bootstrap'),
    ]

    operations = {
        HqRunPython(update_twilio_rates_outgoing),
    }
