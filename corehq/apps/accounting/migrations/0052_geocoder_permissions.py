from django.db import migrations
from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install

from corehq.privileges import GEOCODER


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        GEOCODER,
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0051_hubspot_restrictions'),
    ]

    operations = [
        migrations.RunPython(_grandfather_basic_privs),
    ]
