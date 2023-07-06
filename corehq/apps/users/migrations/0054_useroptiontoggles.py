from django.conf import settings
from django.db import migrations, models

from corehq.apps.users.models import CouchUser, UserOptionToggles
from corehq.toggles import ALL_NAMESPACES, NAMESPACE_USER, Toggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_users():
    toggle = Toggle.cached_get('use_latest_build_cloudcare')
    if not toggle:
        return []
    prefixes = tuple(ns + ':' for ns in ALL_NAMESPACES if ns != NAMESPACE_USER)
    return [u for u in toggle.enabled_users if not u.startswith(prefixes)]


@skip_on_fresh_install
def _upsert_user_option_toggles(apps, schema_editor):
    for username in get_enabled_users():
        django_user = CouchUser(username=username).get_django_user()
        UserOptionToggles.objects.update_or_create(
            user=django_user,
            defaults={'use_latest_build_cloudcare': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0053_userreportingmetadatastaging_fcm_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserOptionToggles',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('use_latest_build_cloudcare', models.BooleanField(default=False)),
                ('user', models.OneToOneField(
                    on_delete=models.deletion.CASCADE,
                    related_name='option_toggles',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.RunPython(
            _upsert_user_option_toggles,
            reverse_code=migrations.RunPython.noop,
            elidable=True
        ),
    ]
