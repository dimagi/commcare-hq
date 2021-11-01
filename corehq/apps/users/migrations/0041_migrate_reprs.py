from django.db import migrations

from corehq.util.django_migrations import run_once_off_migration


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0040_add_repr_and_changed_by_repr'),
    ]

    operations = [
        run_once_off_migration('migrate_reprs')
    ]
