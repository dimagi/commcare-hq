from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def remove_user_data(apps, schema_editor):
    call_command('rm_couch_user_data')


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0070_alter_invitation_tableau_role"),
    ]

    operations = [
        migrations.RunPython(remove_user_data, migrations.RunPython.noop),
    ]
