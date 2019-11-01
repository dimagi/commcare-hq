from collections import defaultdict
from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.util.django_migrations import skip_on_fresh_install


def _update_model(model, domain, domain_forms):
    if model.form_unique_id is None:
        return None

    if domain not in domain_forms:
        domain_forms[domain] = defaultdict(dict)
        apps = get_apps_in_domain(domain)
        for app in apps:
            for module in app.modules:
                for form in module.get_forms():
                    domain_forms[domain][form.unique_id] = app.get_id

    model.app_id = domain_forms[domain].get(model.form_unique_id, None)
    if model.app_id:
        model.save()


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    Call = apps.get_model('ivr', 'Call')
    domain_forms = {}
    for call in Call.objects.filter(form_unique_id__isnull=False).all():
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
