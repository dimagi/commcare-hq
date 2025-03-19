from django.db import migrations

from django_prbac.models import Grant, Role

from corehq import privileges, toggles
from corehq.apps.accounting.utils import (
    get_all_roles_by_slug,
    get_granted_privs_for_grantee,
)
from corehq.util.django_migrations import skip_on_fresh_install

ENTERPRISE_PLAN_ROLE_SLUG = 'enterprise_plan_v0'


@skip_on_fresh_install
def _remove_privilege_from_plan(apps, schema_editor):
    try:
        Role.objects.get(slug=privileges.APPLICATION_ERROR_REPORT).delete()
    except Role.DoesNotExist:
        pass


@skip_on_fresh_install
def _grant_privilege_to_plans(*args, **kwargs):
    # This adds the removed privilege back to the Enterprise plan and
    # is modelled after the ensure_grants function
    try:
        priv_role = Role.objects.get(slug=privileges.APPLICATION_ERROR_REPORT)
    except Role.DoesNotExist:
        priv_role = Role(
            slug=privileges.APPLICATION_ERROR_REPORT,
            name=toggles.APPLICATION_ERROR_REPORT.label,
            description=toggles.APPLICATION_ERROR_REPORT.description,
        )
        priv_role.save()

    grantee_privileges = get_granted_privs_for_grantee()[ENTERPRISE_PLAN_ROLE_SLUG]
    if privileges.APPLICATION_ERROR_REPORT not in grantee_privileges:
        grantee_role = get_all_roles_by_slug()[ENTERPRISE_PLAN_ROLE_SLUG]
        Role.get_cache().clear()
        Grant.objects.create(
            from_role=grantee_role,
            to_role=priv_role,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0091_remove_custom_banner_alerts_feature_flag'),
    ]

    operations = [
        migrations.RunPython(
            _remove_privilege_from_plan,
            reverse_code=_grant_privilege_to_plans,
        ),
    ]
