from django.db import migrations
from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install

from corehq.privileges import APP_USER_PROFILES


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        APP_USER_PROFILES,
        skip_edition='Paused,Community,Standard,Pro',
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0048_friendly_writeoff'),
    ]

    operations = [
        migrations.RunPython(_grandfather_basic_privs),
    ]
