from django.db import migrations

from django_prbac.models import Role, Grant
from corehq.util.django_migrations import skip_on_fresh_install
from corehq import privileges
from corehq.apps.accounting.utils import get_granted_privs_for_grantee, get_all_roles_by_slug

ADVANCED_PLAN_ROLE_SLUG = 'advanced_plan_v0'


@skip_on_fresh_install
def _remove_privilege_from_plan(apps, schema_editor):
    try:
        role = Role.objects.get(slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER)
        role.delete()
    except Role.DoesNotExist:
        pass


@skip_on_fresh_install
def _grant_privilege_to_advanced_plan(*args, **kwargs):
    # This adds the removed privilege back to the Advanced plan
    # and is modelled after the ensure_grants function.
    advanced_plan_privileges = get_granted_privs_for_grantee()[ADVANCED_PLAN_ROLE_SLUG]

    if privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER not in advanced_plan_privileges:
        advanced_plan_role = get_all_roles_by_slug()[ADVANCED_PLAN_ROLE_SLUG]
        priv_role = Role(
            slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER,
            name='Application error report',
            description='Show Application Error Report'
        )
        priv_role.save()
        Role.get_cache().clear()

        # Grant the privilege to the advanced_plan
        Grant.objects.create(
            from_role=advanced_plan_role,
            to_role=priv_role,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0077_case_list_explorer_priv'),
    ]

    operations = [
        migrations.RunPython(
            _remove_privilege_from_plan,
            reverse_code=_grant_privilege_to_advanced_plan,
        ),
    ]
