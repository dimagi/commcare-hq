from django.db import migrations

from corehq.apps.accounting.management.commands.upgrade_software_plan_version import upgrade_software_plan_version
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _upgrade_enterprise_plan_v0_to_v1(apps, schema_editor):
    upgrade_software_plan_version('enterprise_plan_v0', 'enterprise_plan_v1')


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0060_add_help_text_for_is_customer_software_plan'),
    ]

    operations = [
        migrations.RunPython(_upgrade_enterprise_plan_v0_to_v1),
    ]
