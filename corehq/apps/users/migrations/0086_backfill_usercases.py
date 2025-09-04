from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def run_create_usercases(apps, schema_editor):
    call_command('create_usercases')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('users', '0085_usercredential'),
    ]

    operations = [
        migrations.RunPython(run_create_usercases, reverse_code=noop),
    ]
