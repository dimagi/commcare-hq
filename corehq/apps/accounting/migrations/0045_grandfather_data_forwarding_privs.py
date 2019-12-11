# Generated by Django 1.11.21 on 2019-11-27 11:11

from django.core.management import call_command
from django.db import migrations

from corehq.privileges import DATA_FORWARDING
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_data_forwarding_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        DATA_FORWARDING,
        skip_edition='Paused',
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0044_grandfather_odata_privs'),
    ]

    operations = [
        migrations.RunPython(_grandfather_data_forwarding_privs),
    ]
