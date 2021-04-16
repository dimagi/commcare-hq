from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_login_as_all_users_permission(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        if role.permissions.edit_commcare_users:
            role.permissions.login_as_all_users = True
            role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0023_hqapikey_role_id'),
    ]

    operations = [
        migrations.RunPython(migrate_login_as_all_users_permission,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True)
    ]
