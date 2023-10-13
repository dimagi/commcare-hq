from django.db import migrations

from corehq.apps.accounting.bootstrap.config.remove_free_50_sms_sep_2023 import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans


def _bootstrap_new_standard_pricing(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0084_copy_cases_priv'),
    ]

    operations = [
        migrations.RunPython(_bootstrap_new_standard_pricing),
    ]
