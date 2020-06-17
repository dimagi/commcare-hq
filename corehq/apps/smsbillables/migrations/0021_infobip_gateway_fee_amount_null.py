from django.db import migrations

from corehq.apps.smsbillables.models import add_infobip_gateway_fee


def add_infobip_gateway_fee_for_migration(apps, schema_editor):
    add_infobip_gateway_fee(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0020_update_sislog_fees'),
    ]

    operations = [
        migrations.RunPython(add_infobip_gateway_fee_for_migration),
    ]
