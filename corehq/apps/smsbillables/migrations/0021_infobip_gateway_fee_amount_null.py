from django.db import migrations

from corehq.apps.smsbillables.management.commands.bootstrap_infobip_gateway import (
    bootstrap_infobip_gateway,
)

def add_infobip_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_infobip_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0020_update_sislog_fees'),
    ]

    operations = [
        migrations.RunPython(add_infobip_gateway_fee_for_migration),
    ]
