from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.util.django_migrations import skip_on_fresh_install


def _update_model(model, domain, app_id_by_form_unique_id):
    if model.form_unique_id is None:
        return None

    if model.form_unique_id not in app_id_by_form_unique_id:
        apps = get_apps_in_domain(domain)
        for app in apps:
            for module in app.modules:
                for form in module.get_forms():
                    app_id_by_form_unique_id[form.unique_id] = app.get_id

    model.app_id = app_id_by_form_unique_id.get(model.form_unique_id, None)
    if model.app_id:
        model.save()


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    Call = apps.get_model('ivr', 'Call')
    app_id_by_form_unique_id = {}
    for call in Call.objects.filter(form_unique_id__isnull=False).all():
        _update_model(call, call.domain, app_id_by_form_unique_id)


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
