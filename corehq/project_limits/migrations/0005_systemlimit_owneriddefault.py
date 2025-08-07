from django.apps import apps
from django.db import migrations

from corehq.project_limits.const import DEFAULT_OWNER_ID_LIMIT, OWNER_ID_LIMIT_KEY
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _update_owner_id_system_limit(limit):
    SystemLimit = apps.get_model('project_limits', 'SystemLimit')

    try:
        system_limit = SystemLimit.objects.get(key=OWNER_ID_LIMIT_KEY, domain="")
    except SystemLimit.DoesNotExist:
        SystemLimit.objects.create(key=OWNER_ID_LIMIT_KEY, limit=limit)
    else:
        system_limit.limit = limit
        system_limit.save()


def make_migration_fn(limit):
    def migrate(apps, schema_editor):
        _update_owner_id_system_limit(limit)

    return migrate


class Migration(migrations.Migration):
    dependencies = [
        ('project_limits', '0004_systemlimit'),
    ]

    operations = [
        migrations.RunPython(make_migration_fn(DEFAULT_OWNER_ID_LIMIT), reverse_code=make_migration_fn(1000))
    ]
