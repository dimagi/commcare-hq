from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_pinpoint_gateway import (
    bootstrap_pinpoint_gateway,
)

def add_pinpoint_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_pinpoint_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0021_infobip_gateway_fee_amount_null'),
    ]

    operations = [
        migrations.RunPython(add_pinpoint_gateway_fee_for_migration),
    ]
