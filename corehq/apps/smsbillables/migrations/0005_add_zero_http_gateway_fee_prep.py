# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.management.commands.add_zero_http_gateway_fee import \
    add_zero_http_gateway_fee


def add_zero_http_gateway_fee_prep(apps, schema_editor):
    add_zero_http_gateway_fee('635b73026a9a8eab55c77a84bccf6be2', OUTGOING, apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0004_bootstrap_smsgh_rates'),
    ]

    operations = [
        migrations.RunPython(add_zero_http_gateway_fee_prep),
    ]
