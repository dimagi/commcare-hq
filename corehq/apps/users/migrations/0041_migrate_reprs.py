from django.db import migrations

from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_reprs(apps, schema_editor):
    call_command('migrate_reprs')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0040_add_repr_and_changed_by_repr'),
    ]

    operations = [
        migrations.RunPython(_migrate_reprs),
    ]
