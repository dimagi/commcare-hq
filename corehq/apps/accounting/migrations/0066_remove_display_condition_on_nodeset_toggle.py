from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install
from corehq.toggles.models import Toggle
from couchdbkit import ResourceNotFound

TOGGLE_SLUG = "display_condition_on_nodeset"


@skip_on_fresh_install
def _remove_toggle_document(apps, schema_editor):
    try:
        toggle = Toggle.get(TOGGLE_SLUG)
        if toggle:
            toggle.delete()
    except ResourceNotFound:
        print(f"Toggle '{TOGGLE_SLUG}' not found")


@skip_on_fresh_install
def _do_nothing(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0065_phone_apk_heartbeat_privs'),
    ]

    operations = [
        migrations.RunPython(_remove_toggle_document, _do_nothing),
    ]
