from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def populate_sql_user_data(apps, schema_editor):
    call_command('populate_sql_user_data')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0056_add_manage_domain_alerts_permission'),
    ]

    operations = [
        migrations.RunPython(populate_sql_user_data, migrations.RunPython.noop)
    ]
