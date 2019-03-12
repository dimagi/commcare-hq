# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.apps.smsbillables.models import SmsGatewayFeeCriteria
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.messaging.smsbackends.yo.models import SQLYoBackend



def update_http_backend_criteria(apps, schema_editor):
    SmsGatewayFeeCriteria.objects.filter(
        backend_api_id='HTTP',
        backend_instance='7ddf3301c093b793c6020ebf755adb6f'
    ).update(
        backend_api_id=SQLSislogBackend.get_api_id(),
        backend_instance=None,
    )

    SmsGatewayFeeCriteria.objects.filter(
        backend_api_id='HTTP',
        backend_instance='95a4f0929cddb966e292e70a634da716'
    ).update(
        backend_api_id=SQLYoBackend.get_api_id(),
        backend_instance=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0004_bootstrap_smsgh_rates'),
    ]

    operations = {
        migrations.RunPython(update_http_backend_criteria),
    }
