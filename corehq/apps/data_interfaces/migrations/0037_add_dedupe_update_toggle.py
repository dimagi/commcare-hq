from django.db import migrations
from corehq.util.django_migrations import skip_on_fresh_install

from corehq.toggles import CASE_DEDUPE, CASE_DEDUPE_UPDATES, NAMESPACE_DOMAIN
from corehq.toggles.models import Toggle


@skip_on_fresh_install
def add_dedupe_update_toggle(apps, schema_editor):
    for domain in CASE_DEDUPE.get_enabled_domains():
        CASE_DEDUPE_UPDATES.set(domain, enabled=True, namespace=NAMESPACE_DOMAIN)


def reverse(apps, schema_editor):
    toggle = Toggle.cached_get(CASE_DEDUPE_UPDATES.slug)
    toggle.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0036_backfill_dedupe_match_values'),
    ]

    operations = [
        migrations.RunPython(add_dedupe_update_toggle, reverse_code=reverse),
    ]
