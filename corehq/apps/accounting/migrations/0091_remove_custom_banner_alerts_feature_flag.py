# Generated by Django 3.2.23 on 2024-01-30 19:08

from django.db import migrations

from couchdbkit import ResourceNotFound

from corehq.toggles import Toggle
from corehq.toggles.models import generate_toggle_id
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _remove_feature_flag(*args, **kwargs):
    toggle_id = generate_toggle_id(slug='custom_domain_banners')
    try:
        # environments where this toggle has not been used, there won't be a record of it in DB
        toggle = Toggle.get(toggle_id)
    except ResourceNotFound:
        pass
    else:
        toggle.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0090_custom_domain_alerts_priv'),
    ]

    operations = [
        migrations.RunPython(
            _remove_feature_flag,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
