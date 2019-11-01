from collections import defaultdict
from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.sms.models import Keyword, MessagingEvent, MessagingSubEvent
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
    domain_forms = {}

    # KeywordAction
    for keyword in Keyword.objects.all():
        for action in keyword.keywordaction_set.filter(form_unique_id__isnull=False):
            _update_model(action, keyword.domain, domain_forms)

    # MessagingEvent
    for event in MessagingEvent.objects.filter(form_unique_id__isnull=False).all():
        _update_model(event, event.domain, domain_forms)

    # MessagingSubEvent
    for subevent in MessagingSubEvent.objects.filter(form_unique_id__isnull=False).all():
        _update_model(subevent, subevent.parent.domain, domain_forms)


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0036_index_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='keywordaction',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='messagingevent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='messagingsubevent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.RunPython(_populate_app_id,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
