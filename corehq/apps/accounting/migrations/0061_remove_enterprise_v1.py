from django.core.management import call_command
from django.db import migrations

from django_prbac.models import Role

from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
    OldRoleDoesNotExist
)
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _consolidate_enterprise_v1_into_v0(apps, schema_editor):
    try:
        change_role_for_software_plan_version('enterprise_plan_v1', 'enterprise_plan_v0')
    except OldRoleDoesNotExist:
        # no role exists for enterprise_plan_v1 which is fine
        pass

    # after updating software plan versions to reference v0, add release management to enterprise_v0 via boostrap
    call_command('cchq_prbac_bootstrap')
    # delete the enterprise_plan_v1 role now that all active plans have been updated
    role = None
    try:
        role = Role.objects.get(slug='enterprise_plan_v1')
    except Role.DoesNotExist:
        pass
    if role:
        # change_role_for_software_plan_version should ensure there aren't any more versions referencing this role
        role.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0060_add_loadtest_users_priv'),
    ]

    operations = [
        migrations.RunPython(
            _consolidate_enterprise_v1_into_v0,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
