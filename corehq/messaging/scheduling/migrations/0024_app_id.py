from django.db import migrations, models
from itertools import chain

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.util.django_migrations import skip_on_fresh_install


def _update_model(model, domain):
    if model.form_unique_id is None:
        return None

    model.app_id = get_app_id_from_form_unique_id(domain, model.form_unique_id)
    if model.app_id:
        model.save()


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    for schedule in chain(AlertSchedule.objects.all(), TimedSchedule.objects.all()):
        for event in schedule.memoized_events:
            if event.sms_survey_content:
                _update_model(event.sms_survey_content, schedule.domain)
            if event.ivr_survey_content:
                _update_model(event.ivr_survey_content, schedule.domain)


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
