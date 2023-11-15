from django.db import migrations

from corehq.motech.repeaters.migration_utils import repair_repeaters_with_whitelist_bug
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _fix_broken_repeaters(apps, schema_editor):
    repair_repeaters_with_whitelist_bug()


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0003_id_fields'),
    ]

    operations = [
        migrations.RunPython(_fix_broken_repeaters, reverse_code=migrations.RunPython.noop)
    ]
