from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_download_reports_permissions(apps, schema_editor):
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        role = UserRole.wrap(role_doc)

        role.permissions.download_reports = True
        role.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0030_userhistory_user_upload_record'),
    ]

    operations = [
        migrations.RunPython(migrate_download_reports_permissions, migrations.RunPython.noop)
    ]
