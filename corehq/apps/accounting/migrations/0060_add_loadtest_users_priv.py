from django.db import migrations
from django.core.management import call_command

from corehq.privileges import LOADTEST_USERS
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        LOADTEST_USERS,
        skip_edition='Paused,Community,Standard',
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0059_add_lite_release_management_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_basic_privs,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
