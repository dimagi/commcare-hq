import traceback
from django.db import migrations

from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_download_reports_permissions(apps, schema_editor):
    try:
        call_command(
            "add_download_reports_permission",
        )
    except Exception:
        traceback.print_exc()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0031_delete_domainpermissionsmirror'),
    ]

    operations = [
        migrations.RunPython(migrate_download_reports_permissions, migrations.RunPython.noop)
    ]
