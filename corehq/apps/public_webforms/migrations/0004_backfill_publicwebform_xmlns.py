from couchdbkit import ResourceNotFound
from django.db import migrations

from corehq.apps.app_manager.models import Application
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _backfill_xmlns(apps, schema_editor):
    backfill_xmlns(apps.get_model('public_webforms', 'PublicWebform'))


def backfill_xmlns(PublicWebform):
    db = Application.get_db()
    for webform in PublicWebform.objects.filter(xmlns=''):
        xmlns = _published_form_xmlns(db, webform)
        if xmlns:
            webform.xmlns = xmlns
        else:
            webform.is_disabled = True
        webform.save()


def _published_form_xmlns(db, webform):
    try:
        build = db.get(webform.app_build_id)
    except ResourceNotFound:
        return None
    if build.get('domain') != webform.domain:
        return None
    for module in build.get('modules', []):
        for form in module.get('forms', []):
            if form.get('unique_id') == webform.form_unique_id:
                return form.get('xmlns')
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('public_webforms', '0003_publicwebform_published_form'),
    ]

    operations = [
        migrations.RunPython(_backfill_xmlns, reverse_code=migrations.RunPython.noop),
    ]
