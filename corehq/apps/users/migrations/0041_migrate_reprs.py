from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_reprs(apps, schema_editor):
    call_command('migrate_reprs')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0040_add_repr_and_changed_by_repr'),
    ]

    operations = [
        migrations.RunPython(_add_reprs,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
