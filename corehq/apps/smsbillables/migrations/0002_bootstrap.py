# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
from django.core.management import call_command

from dimagi.utils.couch import sync_docs

import corehq.apps.sms.models as sms_models
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway import \
    bootstrap_grapevine_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_mach_gateway import \
    bootstrap_mach_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_tropo_gateway import \
    bootstrap_tropo_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_twilio_gateway import \
    bootstrap_twilio_gateway
from corehq.apps.smsbillables.management.commands.bootstrap_unicel_gateway import \
    bootstrap_unicel_gateway


def sync_sms_docs(apps, schema_editor):
    # hack: manually force sync SMS design docs before
    # we try to load from them. the bootstrap commands are dependent on these.
    # import ipdb; ipdb.set_trace()
    sync_docs.sync(apps.get_app_config('sms').get_models(), verbosity=2)


def bootstrap_currency(apps, schema_editor):
    Currency = apps.get_model("accounting", "Currency")
    Currency.objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    Currency.objects.get_or_create(code='EUR')
    Currency.objects.get_or_create(code='INR')


def bootstrap_sms(apps, schema_editor):
    bootstrap_grapevine_gateway(apps)
    bootstrap_mach_gateway(apps)
    bootstrap_tropo_gateway(apps)
    bootstrap_twilio_gateway(apps)
    bootstrap_unicel_gateway(apps)
    call_command('bootstrap_usage_fees')


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0001_initial'),
        ('sms', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sync_sms_docs),
        migrations.RunPython(bootstrap_currency),
        migrations.RunPython(bootstrap_sms),
    ]
