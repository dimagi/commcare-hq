from django.db import migrations, models

from corehq.apps.domain.models import DomainOptionToggles
from corehq.toggles import NAMESPACE_DOMAIN, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_domains():
    toggle = Toggle.cached_get('use_latest_build_cloudcare')
    if not toggle:
        return []
    prefix = NAMESPACE_DOMAIN + ':'
    skip = len(prefix)
    return [d[skip:] for d in toggle.enabled_users if d.startswith(prefix)]


@skip_on_fresh_install
def _upsert_domain_option_toggles(apps, schema_editor):
    for domain in get_enabled_domains():
        DomainOptionToggles.objects.update_or_create(
            domain=domain,
            defaults={'use_latest_build_cloudcare': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0014_appreleasemodesetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='DomainOptionToggles',
            fields=[
                ('domain', models.CharField(
                    max_length=126,
                    primary_key=True,
                    serialize=False,
                )),
                ('use_latest_build_cloudcare', models.BooleanField(default=False)),
            ],
        ),
        migrations.RunPython(
            _upsert_domain_option_toggles,
            reverse_code=migrations.RunPython.noop,
            elidable=True
        ),
    ]
