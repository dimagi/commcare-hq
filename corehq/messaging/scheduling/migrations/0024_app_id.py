from django.core.management import call_command
from django.db import migrations, models

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    call_command('populate_app_id_for_scheduling')


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0023_add_remaining_content_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='ivrsurveycontent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='smssurveycontent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.RunPython(_populate_app_id,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
