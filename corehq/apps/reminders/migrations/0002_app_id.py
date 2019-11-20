from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    call_command('populate_app_id_for_survey_keyword')


class Migration(migrations.Migration):

    dependencies = [
        ('reminders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_populate_app_id,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
