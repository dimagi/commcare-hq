from django.db import migrations

from corehq.apps.es import UserES
from corehq.apps.users.models import WebUser
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def fix_users(apps, schema_editor):
    user_ids = with_progress_bar(_get_admins_with_roles())
    iter_update(WebUser.get_db(), _remove_role, user_ids, verbose=True)


def _get_admins_with_roles():
    # domain_memberships isn't a nested mapping in ES, so this only checks that
    # they have a domain membership that's an admin, and one with a role_id,
    # not that it's both on the same membership
    return (UserES()
            .web_users()
            .term('domain_memberships.is_admin', True)
            .non_null('domain_memberships.role_id')
            .get_ids())


def _remove_role(user_doc):
    changed = False
    for dm in user_doc['domain_memberships']:
        if dm['is_admin'] and dm['role_id']:
            dm['role_id'] = None
            changed = True

    if changed:
        return DocUpdate(user_doc)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_roles_permissions_update'),
    ]

    operations = [
        migrations.RunPython(fix_users, reverse_code=migrations.RunPython.noop, elidable=True)
    ]
