# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations

from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee
from corehq.messaging.smsbackends.twilio.models import TwilioBackend


def add_twilio_gateway_fee(apps, schema_editor):
    default_currency, _ = apps.get_model('accounting', 'Currency').objects.get_or_create(code=settings.DEFAULT_CURRENCY)

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            TwilioBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0005_smsbillable_direct_gateway_fee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsgatewayfee',
            name='amount',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
        migrations.RunPython(add_twilio_gateway_fee, reverse_code=lambda apps, schema_editor: None),
    ]
