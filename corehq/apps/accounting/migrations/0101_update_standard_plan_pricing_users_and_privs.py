from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.bootstrap.config.standard_update_april_2025 import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans


def _add_standard_plan_v2_role(apps, schema_editor):
    call_command('cchq_prbac_bootstrap', verbose=True)


def _bootstrap_new_standard_pricing(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0100_alter_customerinvoicecommunicationhistory_communication_type_and_more'),
    ]

    operations = [
        migrations.RunPython(_add_standard_plan_v2_role),
        migrations.RunPython(_bootstrap_new_standard_pricing),
    ]
