from django.db import migrations
from django.core.management import call_command

from corehq.privileges import LITE_RELEASE_MANAGEMENT
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        LITE_RELEASE_MANAGEMENT,
        skip_edition='Paused,Community,Standard',
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0058_delete_linked_projects_role'),
    ]

    operations = [
        migrations.RunPython(_grandfather_basic_privs),
    ]
