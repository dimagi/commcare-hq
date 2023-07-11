from django.db import migrations

from corehq.apps.domain.models import LATEST_BUILD_ALWAYS, Domain
from corehq.toggles import NAMESPACE_DOMAIN, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_domain_names():
    toggle = Toggle.cached_get('use_latest_build_cloudcare')
    if not toggle:
        return []
    prefix = NAMESPACE_DOMAIN + ':'
    skip = len(prefix)
    return [d[skip:] for d in toggle.enabled_users if d.startswith(prefix)]


@skip_on_fresh_install
def _save_toggle_to_domain(apps, schema_editor):
    for domain_name in get_enabled_domain_names():
        domain_obj = Domain.get_by_name(domain_name)
        domain_obj.latest_build_in_web_apps = LATEST_BUILD_ALWAYS
        domain_obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0014_appreleasemodesetting'),
    ]

    operations = [
        migrations.RunPython(
            _save_toggle_to_domain,
            reverse_code=migrations.RunPython.noop,
            elidable=True
        ),
    ]
