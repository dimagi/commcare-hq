from django.db import migrations
from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0055_linked_projects'),
    ]

    operations = [
        migrations.RunPython(_grandfather_basic_privs),
    ]
