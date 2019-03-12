# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_smsgh_gateway import \
    bootstrap_smsgh_gateway



def create_smsgh_rates(apps, schema_editor):
    bootstrap_smsgh_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0003_update_twilio_rates_outgoing'),
    ]

    operations = {
        migrations.RunPython(create_smsgh_rates),
    }
