# Generated by Django 2.2.13 on 2020-09-24 17:53

from django.db import migrations

from couchdbkit import ResourceNotFound

from corehq.apps.domain.models import Domain
from corehq.apps.toggle_ui.models import generate_toggle_id, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _set_use_livequery(apps, schema_editor):
    toggle_id = generate_toggle_id('livequery_sync')
    try:
        toggle_doc = Toggle.get_db().get(toggle_id)
    except ResourceNotFound:
        # Flag isn't enabled for anyone on this server
        return
    for user in toggle_doc.get('enabled_users', []):
        domain_obj = Domain.get_by_name(user.split('domain:')[1])
        if domain_obj and not domain_obj.use_livequery:
            domain_obj.use_livequery = True
            domain_obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0007_auto_20200924_1753'),
    ]

    operations = [
        migrations.RunPython(_set_use_livequery,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
