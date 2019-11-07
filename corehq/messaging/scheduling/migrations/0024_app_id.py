from django.db import migrations, models
from itertools import chain

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.util.django_migrations import skip_on_fresh_install


def _update_model(model, domain, domain_forms):
    if model.form_unique_id is None:
        return None

    if domain not in domain_forms:
        domain_forms[domain] = {}
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
    domain_forms = {}
    for schedule in chain(AlertSchedule.objects.all(), TimedSchedule.objects.all()):
        for event in schedule.memoized_events:
            if event.sms_survey_content:
                _update_model(event.sms_survey_content, schedule.domain, domain_forms)
            if event.ivr_survey_content:
                _update_model(event.ivr_survey_content, schedule.domain, domain_forms)


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
