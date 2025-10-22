from django.db import migrations

from couchdbkit import ResourceNotFound

from corehq.toggles import Toggle
from corehq.toggles.models import generate_toggle_id
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _remove_feature_flag(*args, **kwargs):
    toggle_id = generate_toggle_id(slug='usercases_for_web_users')
    try:
        toggle = Toggle.get(toggle_id)
    except ResourceNotFound:
        pass
    else:
        toggle.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('toggles', '0002_assign_permissions_superusers'),
    ]

    operations = [
        migrations.RunPython(
            _remove_feature_flag,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
