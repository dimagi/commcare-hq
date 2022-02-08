from django.core.management import call_command
from django.db import migrations

from django_prbac.models import Role

from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
)
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _consolidate_enterprise_v1_into_v0(apps, schema_editor):
    change_role_for_software_plan_version('enterprise_plan_v1', 'enterprise_plan_v0')
    # after updating software plan versions to reference v0, add release management to enterprise_v0 via boostrap
    call_command('cchq_prbac_bootstrap')
    # delete the enterprise_plan_v1 role now that all active plans have been updated
    role = None
    try:
        role = Role.objects.get(slug='enterprise_plan_v1')
    except Role.DoesNotExist:
        pass
    if role:
        # will delete all software plan versions that reference this role as well
        role.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0059_add_lite_release_management_priv'),
    ]

    operations = [
        migrations.RunPython(_consolidate_enterprise_v1_into_v0),
    ]
