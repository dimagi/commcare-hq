from django.core.management import call_command
from django.db import migrations, models

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    Call = apps.get_model('ivr', 'Call')
    if Call.objects.exists():
        call_command('populate_app_id_for_call')


class Migration(migrations.Migration):

    dependencies = [
        ('ivr', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.RunPython(_populate_app_id,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
