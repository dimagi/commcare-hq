from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def remove_location_from_user_data(apps, schema_editor):
    call_command('rm_location_from_user_data')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0072_remove_invitation_supply_point'),
    ]

    operations = [
        migrations.RunPython(remove_location_from_user_data, migrations.RunPython.noop),
    ]
