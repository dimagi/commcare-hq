from django.conf import settings
from django.db import migrations
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee
from corehq.apps.smsbillables.models import SmsGatewayFeeCriteria
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.messaging.smsbackends.yo.models import SQLYoBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from decimal import Decimal

from corehq.apps.smsbillables.management.commands.add_moz_zero_charge import (
    add_moz_zero_charge,
)
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway import (
    bootstrap_grapevine_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_grapevine_gateway_update import (
    bootstrap_grapevine_gateway_update,
)
from corehq.apps.smsbillables.management.commands.bootstrap_mach_gateway import (
    bootstrap_mach_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_moz_gateway import (
    bootstrap_moz_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_telerivet_gateway import (
    bootstrap_telerivet_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_test_gateway import (
    bootstrap_test_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_tropo_gateway import (
    bootstrap_tropo_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_unicel_gateway import (
    bootstrap_unicel_gateway,
)
from corehq.apps.smsbillables.management.commands.bootstrap_usage_fees import (
    bootstrap_usage_fees,
)
from corehq.apps.smsbillables.management.commands.bootstrap_yo_gateway import (
    bootstrap_yo_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_smsgh_gateway import (
    bootstrap_smsgh_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_gateway_fees import (
    bootstrap_twilio_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_apposit_gateway import (
    bootstrap_apposit_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_icds_gateway import (
    bootstrap_icds_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_gateway_fees import (
    bootstrap_infobip_gateway,
)

from corehq.apps.smsbillables.management.commands.bootstrap_gateway_fees import (
    bootstrap_pinpoint_gateway,
)


def create_icds_rates(apps, schema_editor):
    bootstrap_icds_gateway(apps)


def add_twilio_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_twilio_gateway(apps)


def create_apposit_rates(apps, schema_editor):
    bootstrap_apposit_gateway(apps)


def add_infobip_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_infobip_gateway(apps)


def add_pinpoint_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_pinpoint_gateway(apps)


def update_http_backend_criteria(apps, schema_editor):
    SmsGatewayFeeCriteria.objects.filter(
        backend_api_id='HTTP',
        backend_couch_id='7ddf3301c093b793c6020ebf755adb6f'
    ).update(
        backend_api_id=SQLSislogBackend.get_api_id(),
        backend_couch_id=None,
    )

    SmsGatewayFeeCriteria.objects.filter(
        backend_api_id='HTTP',
        backend_couch_id='95a4f0929cddb966e292e70a634da716'
    ).update(
        backend_api_id=SQLYoBackend.get_api_id(),
        backend_couch_id=None,
    )


def deactivate_hardcoded_twilio_gateway_fees(apps, schema_editor):
    SmsGatewayFeeCriteria = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria')

    to_deactivate = SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
        country_code__isnull=False,
        is_active=True,
    )
    remaining = SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
    ).exclude(
        id__in=to_deactivate.values('id')
    )
    assert remaining.count() == 2
    assert remaining.filter(country_code=None).count() == 2
    to_deactivate.update(is_active=False)

    assert SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
        is_active=True,
    ).count() == 2
    assert SmsGatewayFeeCriteria.objects.filter(
        backend_api_id=SQLTwilioBackend.get_api_id(),
        country_code__isnull=True,
        is_active=True,
    ).count() == 2


def update_sislog_vodacom_mozambique_fees(apps, schema_editor):
    mzn, _ = apps.get_model('accounting', 'Currency').objects.get_or_create(code='MZN')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee')
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria')

    country_code = 258
    for prefix in ['84', '85']:
        SmsGatewayFee.create_new(
            SQLSislogBackend.get_api_id(),
            INCOMING,
            Decimal('2.0'),
            country_code=country_code,
            prefix=prefix,
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )

        SmsGatewayFee.create_new(
            SQLSislogBackend.get_api_id(),
            OUTGOING,
            Decimal('0.35'),
            country_code=country_code,
            prefix=prefix,
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )


def create_smsgh_rates(apps, schema_editor):
    bootstrap_smsgh_gateway(apps)


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
    bootstrap_unicel_gateway(apps)
    bootstrap_usage_fees(apps)
    bootstrap_moz_gateway(apps)
    bootstrap_test_gateway(apps)
    bootstrap_telerivet_gateway(apps)
    bootstrap_yo_gateway(apps)
    add_moz_zero_charge(apps)
    bootstrap_grapevine_gateway_update(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0024_auto_20200727_1611'),
        ('sms', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sync_sms_docs),
        migrations.RunPython(bootstrap_currency),
        migrations.RunPython(bootstrap_sms),
        migrations.RunPython(create_smsgh_rates),
        migrations.RunPython(update_http_backend_criteria),
        migrations.RunPython(add_twilio_gateway_fee_for_migration),
        migrations.RunPython(create_apposit_rates),
        migrations.RunPython(create_icds_rates),
        migrations.RunPython(deactivate_hardcoded_twilio_gateway_fees),
        migrations.RunPython(update_sislog_vodacom_mozambique_fees),
        migrations.RunPython(add_infobip_gateway_fee_for_migration),
        migrations.RunPython(add_pinpoint_gateway_fee_for_migration),
    ]
