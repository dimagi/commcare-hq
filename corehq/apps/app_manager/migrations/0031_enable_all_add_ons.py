from django.db import migrations

from corehq.apps.app_manager.add_ons import _ADD_ONS
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.toggles import StaticToggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_domains():
    """
    Returns the domains that had the ENABLE_ALL_ADD_ONS toggle enabled,
    even after the toggle has been deleted.
    """
    # Allows migration to be run before or after code changes
    toggle = StaticToggle('enable_all_add_ons', '', '')
    return toggle.get_enabled_domains()


@skip_on_fresh_install
def enable_all_add_ons(apps, schema_editor):
    """
    Enable all add-ons for all applications in all domains with the
    ENABLE_ALL_ADD_ONS toggle enabled.
    """
    all_add_ons_enabled = {slug: True for slug in _ADD_ONS.keys()}

    for domain_name in get_enabled_domains():
        if not Domain.get_by_name(domain_name):
            continue

        app_ids = get_app_ids_in_domain(domain_name)
        for app_id in app_ids:
            app = Application.get(app_id)
            if app and not app.is_remote_app():
                app.add_ons.update(all_add_ons_enabled)
                app.save()


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0030_credentialapplication'),
    ]

    operations = [
        migrations.RunPython(
            enable_all_add_ons,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
