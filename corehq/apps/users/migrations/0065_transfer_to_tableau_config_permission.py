from django.db import migrations
from django.db.models import Q

from dimagi.utils.chunked import chunked
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from corehq.apps.users.models import HqPermissions
from corehq.toggles import TABLEAU_USER_SYNCING
from corehq.apps.users.models import UserRole


@skip_on_fresh_install
def transfer_web_user_permission_to_tableau_config_permission(apps, schema_editor):
    user_role_ids_to_migrate = get_user_role_ids_to_migrate()

    for chunk in with_progress_bar(chunked(user_role_ids_to_migrate, 1000),
                                length=len(user_role_ids_to_migrate)):
        for role in UserRole.objects.filter(id__in=chunk):
            permissions = role.permissions
            if permissions.edit_web_users:
                permissions.edit_user_tableau_config = True
                permissions.view_user_tableau_config = True
            elif permissions.view_web_users:
                permissions.view_user_tableau_config = True

            role.set_permissions(permissions.to_list())


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0064_add_edit_view_tableau_config_permissions'),
    ]

    operations = [
        migrations.RunPython(transfer_web_user_permission_to_tableau_config_permission, migrations.RunPython.noop)
    ]


def get_user_role_ids_to_migrate():
    tableau_user_syncing_domains = TABLEAU_USER_SYNCING.get_enabled_domains()

    return (UserRole.objects
        .filter(domain__in=tableau_user_syncing_domains)
        .exclude(role_already_migrated())
        .filter(role_has_view_web_user_permission())
        .distinct()
        .values_list("id", flat=True))


def role_already_migrated() -> Q:
    return Q(rolepermission__permission_fk__value=HqPermissions.view_user_tableau_config.name)


def role_has_view_web_user_permission() -> Q:
    can_edit_web_user = Q(rolepermission__permission_fk__value=HqPermissions.edit_web_users.name)
    # Roles that can edit should also have view permission so this is redundant but I am including it just
    # for safety.
    can_view_web_user = Q(rolepermission__permission_fk__value=HqPermissions.view_web_users.name)
    return (can_edit_web_user | can_view_web_user)
