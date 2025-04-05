from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.bootstrap.config.standard_update_april_2025 import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.privileges import USERCASE, ZAPIER_INTEGRATION
from corehq.util.django_migrations import skip_on_fresh_install


def _bootstrap_new_standard_pricing(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


@skip_on_fresh_install
def _remove_usercase_and_zapier_from_standard_and_below(apps, schema_editor):
    call_command(
        'cchq_prbac_revoke_privs',
        [USERCASE, ZAPIER_INTEGRATION],
        skip_edition='Pro,Advanced,Enterprise',
        delete_privs=False,
        check_privs_exist=True,
        verbose=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0100_alter_customerinvoicecommunicationhistory_communication_type_and_more'),
    ]

    operations = [
        migrations.RunPython(_bootstrap_new_standard_pricing),
        migrations.RunPython(_remove_usercase_and_zapier_from_standard_and_below),
    ]
