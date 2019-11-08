from django.db import migrations, models

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    Call = apps.get_model('ivr', 'Call')
    for call in Call.objects.distinct('domain', 'form_unique_id').filter(app_id__isnull=True,
                                                                         form_unique_id__isnull=False):
        app_id = get_app_id_from_form_unique_id(call.form_unique_id)
        if app_id:
            Call.objects.filter(form_unique_id=call.form_unique_id).update(app_id=app_id)


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
