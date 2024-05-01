from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def grant_web_apps_to_default_mobile_worker_role(apps, schema_editor):
    call_command('grant_web_apps_to_default_mobile_worker_role')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0062_add_web_apps_groups_permission_flag'),
    ]

    operations = [
        migrations.RunPython(grant_web_apps_to_default_mobile_worker_role, migrations.RunPython.noop),
    ]
