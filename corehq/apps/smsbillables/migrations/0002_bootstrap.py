# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.conf import settings
from django.db import migrations

from corehq.apps.smsbillables.management.commands.add_moz_zero_charge import \
    add_moz_zero_charge
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway import \
    bootstrap_grapevine_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway_update import \
    bootstrap_grapevine_gateway_update
from corehq.apps.smsbillables.management.commands.bootstrap_mach_gateway import \
    bootstrap_mach_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_moz_gateway import \
    bootstrap_moz_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_telerivet_gateway import \
    bootstrap_telerivet_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_test_gateway import \
    bootstrap_test_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_tropo_gateway import \
    bootstrap_tropo_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_twilio_gateway import \
    bootstrap_twilio_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_twilio_gateway_incoming import \
    bootstrap_twilio_gateway_incoming
from corehq.apps.smsbillables.management.commands.bootstrap_unicel_gateway import \
    bootstrap_unicel_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_usage_fees import \
    bootstrap_usage_fees
from corehq.apps.smsbillables.management.commands.bootstrap_yo_gateway import \
    bootstrap_yo_gateway
from corehq.sql_db.operations import HqRunPython


def sync_sms_docs(apps, schema_editor):
    # hack: manually force sync SMS design docs before
    # we try to load from them. the bootstrap commands are dependent on these.
    # import ipdb; ipdb.set_trace()
    pass


def bootstrap_currency(apps, schema_editor):
    Currency = apps.get_model("accounting", "Currency")
    Currency.objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    Currency.objects.get_or_create(code='EUR')
    Currency.objects.get_or_create(code='INR')


def bootstrap_sms(apps, schema_editor):
    bootstrap_grapevine_gateway(apps)
    bootstrap_mach_gateway(apps)
    bootstrap_tropo_gateway(apps)
    bootstrap_twilio_gateway(
        apps,
        'corehq/apps/smsbillables/management/commands/pricing_data/twilio-rates-2015_10_06.csv'
    )
    bootstrap_unicel_gateway(apps)
    bootstrap_usage_fees(apps)
    bootstrap_moz_gateway(apps)
    bootstrap_test_gateway(apps)
    bootstrap_telerivet_gateway(apps)
    bootstrap_twilio_gateway_incoming(apps)
    bootstrap_yo_gateway(apps)
    add_moz_zero_charge(apps)
    bootstrap_grapevine_gateway_update(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0001_initial'),
        ('sms', '0001_initial'),
    ]

    operations = [
        HqRunPython(sync_sms_docs),
        HqRunPython(bootstrap_currency),
        HqRunPython(bootstrap_sms),
    ]
