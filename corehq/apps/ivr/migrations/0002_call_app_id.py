from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.util.django_migrations import skip_on_fresh_install


def _update_model(model, instance, domain_forms):
    domain = instance.domain
    if domain not in domain_forms:
        apps = get_apps_in_domain(domain)
        domain_forms[domain] = {}
        for app in apps:
            for module in app.modules:
                for form in module.get_forms():
                    domain_forms[domain][form.unique_id] = app.get_id

    app_id = domain_forms[domain].get(instance.form_unique_id, None)
    if app_id:
        model.objects.filter(form_unique_id=instance.form_unique_id).update(app_id=app_id)


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    domain_forms = {}
    Call = apps.get_model('ivr', 'Call')
    for call in Call.objects.distinct('domain', 'form_unique_id').filter(form_unique_id__isnull=False):
        _update_model(call, call.domain, domain_forms)


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
