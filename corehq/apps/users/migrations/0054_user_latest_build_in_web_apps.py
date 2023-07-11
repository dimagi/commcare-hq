from django.db import migrations

from corehq.apps.users.models import CouchUser
from corehq.toggles import ALL_NAMESPACES, NAMESPACE_USER, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_usernames():
    toggle = Toggle.cached_get('use_latest_build_cloudcare')
    if not toggle:
        return []
    prefixes = tuple(ns + ':' for ns in ALL_NAMESPACES if ns != NAMESPACE_USER)
    return [u for u in toggle.enabled_users if not u.startswith(prefixes)]


@skip_on_fresh_install
def _save_toggle_to_user(apps, schema_editor):
    for username in get_enabled_usernames():
        user = CouchUser(username=username)
        user.latest_build_in_web_apps = True
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0053_userreportingmetadatastaging_fcm_token'),
    ]

    operations = [
        migrations.RunPython(
            _save_toggle_to_user,
            reverse_code=migrations.RunPython.noop,
            elidable=True
        ),
    ]
