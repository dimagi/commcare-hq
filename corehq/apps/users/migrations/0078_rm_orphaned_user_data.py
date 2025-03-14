from django.db import migrations
from django.core.management import call_command

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def remove_orphaned_user_data():
    call_command('rm_orphaned_user_data')


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0077_invitationhistory"),
    ]

    operations = [migrations.RunPython(remove_orphaned_user_data, migrations.RunPython.noop)]
