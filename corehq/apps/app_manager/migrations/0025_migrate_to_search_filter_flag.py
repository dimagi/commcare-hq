import traceback
from django.db import migrations

from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_to_search_filter_flag(apps, schema_editor):
    try:
        call_command(
            "flag_domains_using_search_filter",
        )
    except Exception:
        traceback.print_exc()


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0024_applicationreleaselog_info'),
    ]

    operations = [
        migrations.RunPython(migrate_to_search_filter_flag, migrations.RunPython.noop)
    ]
