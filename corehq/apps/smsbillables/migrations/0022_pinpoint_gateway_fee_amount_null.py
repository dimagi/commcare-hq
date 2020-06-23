from django.db import migrations

from corehq.apps.smsbillables.models import add_pinpoint_gateway_fee


def add_pinpoint_gateway_fee_for_migration(apps, schema_editor):
    add_pinpoint_gateway_fee(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0021_infobip_gateway_fee_amount_null'),
    ]

    operations = [
        migrations.RunPython(add_pinpoint_gateway_fee_for_migration),
    ]
