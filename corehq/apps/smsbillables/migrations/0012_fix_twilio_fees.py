# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, transaction
from django.db.models import Count

from corehq.apps.sms.models import SMS
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend


def deactivate_twilio_gateway_fee_criteria(apps, schema_editor):
    SmsGatewayFeeCriteria = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria')

    SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
        smsgatewayfee__amount__isnull=False,
    ).update(
        is_active=False
    )

    assert SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
        is_active=True,
    ).count() == 2


def reset_twilio_gateway_fees(apps, schema_editor):
    SmsBillable = apps.get_model('smsbillables', 'SmsBillable')

    old_twilio_billables = SmsBillable.objects.filter(
        gateway_fee__criteria__backend_api_id=SQLTwilioBackend.get_api_id(),
        gateway_fee__criteria__is_active=False,
        is_valid=True,
    )
    with transaction.atomic():
        old_twilio_billables.update(is_valid=False)
        for log_id in set(map(
            lambda field_to_value: field_to_value['log_id'],
            old_twilio_billables.values('log_id')
        )):
            SmsBillable.create(SMS.objects.get(couch_id=log_id))

    assert not SmsBillable.objects.filter(
        gateway_fee__criteria__backend_api_id=SQLTwilioBackend.get_api_id(),
        is_valid=True,
    ).exclude(
        multipart_count=1
    ).exists()
    assert not SmsBillable.objects.filter(
        gateway_fee__criteria__backend_api_id=SQLTwilioBackend.get_api_id(),
        is_valid=True,
    ).values('log_id').annotate(Count('id')).filter(id__count__gt=1).exists()


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0011_smsgatewayfeecriteria_is_active'),
    ]

    operations = [
        migrations.RunPython(deactivate_twilio_gateway_fee_criteria),
        migrations.RunPython(reset_twilio_gateway_fees),
    ]
