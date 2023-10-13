from django.db import migrations

from django_prbac.models import Role, Grant
from corehq.util.django_migrations import skip_on_fresh_install
from corehq import privileges
from corehq.apps.accounting.utils import get_granted_privs_for_grantee, get_all_roles_by_slug

ADVANCED_PLAN_ROLE_SLUG = 'advanced_plan_v0'
ENTERPRISE_PLAN_ROLE_SLUG = 'enterprise_plan_v0'


@skip_on_fresh_install
def _remove_privilege_from_plan(apps, schema_editor):
    try:
        role = Role.objects.get(slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER)
        role.delete()
    except Role.DoesNotExist:
        pass


@skip_on_fresh_install
def _grant_privilege_to_plans(*args, **kwargs):
    # This adds the removed privilege back to the Advanced and
    # Enterprise plans and is modelled after the ensure_grants function.
    try:
        priv_role = Role.objects.get(slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER)
    except Role.DoesNotExist:
        priv_role = Role(
            slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER,
            name='Additional "Owner (Location)" property in report builder reports.',
            description='Show an additional "Owner (Location)" property in report builder reports.'
        )
        priv_role.save()

    grants_to_create = []
    for grantee_slug in [ADVANCED_PLAN_ROLE_SLUG, ENTERPRISE_PLAN_ROLE_SLUG]:
        grantee_privileges = get_granted_privs_for_grantee()[grantee_slug]

        if privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER not in grantee_privileges:
            grantee_role = get_all_roles_by_slug()[grantee_slug]
            grants_to_create.append(
                Grant(
                    from_role=grantee_role,
                    to_role=priv_role,
                )
            )
    if grants_to_create:
        Role.get_cache().clear()
        Grant.objects.bulk_create(grants_to_create)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0077_case_list_explorer_priv'),
    ]

    operations = [
        migrations.RunPython(
            _remove_privilege_from_plan,
            reverse_code=_grant_privilege_to_plans,
        ),
    ]
