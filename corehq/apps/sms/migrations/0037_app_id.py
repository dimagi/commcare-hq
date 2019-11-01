from django.db import migrations, models

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.util.django_migrations import skip_on_fresh_install


def _populate_domain_forms(domain, domain_forms):
    if domain not in domain_forms:
        domain_forms[domain] = {}
        apps = get_apps_in_domain(domain)
        for app in apps:
            for module in app.modules:
                for form in module.get_forms():
                    domain_forms[domain][form.unique_id] = app.get_id


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    domain_forms = {}

    Keyword = apps.get_model('sms', 'Keyword')
    KeywordAction = apps.get_model('sms', 'KeywordAction')
    for keyword in Keyword.objects.distinct('domain'):
        for action in keyword.keywordaction_set.filter(form_unique_id__isnull=False):
            _populate_domain_forms(keyword.domain, domain_forms)
            app_id = domain_forms[keyword.domain].get(action.form_unique_id, None)
            if app_id:
                KeywordAction.objects.filter(form_unique_id=action.form_unique_id).update(app_id=app_id)

    MessagingEvent = apps.get_model('sms', 'MessagingEvent')
    for event in MessagingEvent.objects.distinct('domain', 'form_unique_id'):
        if event.form_unique_id:
            _populate_domain_forms(event.domain, domain_forms)
            app_id = domain_forms[event.domain].get(event.form_unique_id, None)
            if app_id:
                MessagingEvent.objects.filter(form_unique_id=event.form_unique_id).update(app_id=app_id)

    MessagingSubEvent = apps.get_model('sms', 'MessagingSubEvent')
    for subevent in MessagingSubEvent.objects.distinct('parent__domain', 'form_unique_id'):
        if subevent.form_unique_id:
            _populate_domain_forms(subevent.parent.domain, domain_forms)
            app_id = domain_forms[subevent.parent.domain].get(subevent.form_unique_id, None)
            if app_id:
                MessagingSubEvent.objects.filter(form_unique_id=subevent.form_unique_id).update(app_id=app_id)


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
