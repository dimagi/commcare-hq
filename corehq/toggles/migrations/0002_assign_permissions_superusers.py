from django.contrib.auth.models import User
from django.db import migrations

from corehq.toggles import ALL_TAGS
from corehq.toggles.sql_models import ToggleEditPermission
from corehq.util.django_migrations import skip_on_fresh_install


# This migration assigns edit permissions for all toggle tags to superusers to maintain consistency
# with the current behavior.

@skip_on_fresh_install
def _assign_all_toggle_edit_permissions_to_superusers(apps, schema_editor):
    superusers = User.objects.filter(is_superuser=True).values_list('username', flat=True)
    for tag in ALL_TAGS:
        toggle_permission = ToggleEditPermission.objects.get_by_tag_slug(tag.slug)
        if not toggle_permission:
            toggle_permission = ToggleEditPermission(tag_slug=tag.slug)
        toggle_permission.add_users(list(superusers))


def _reverse(apps, schema_editor):
    superusers = User.objects.filter(is_superuser=True).values_list('username', flat=True)
    for tag in ALL_TAGS:
        toggle_permission = ToggleEditPermission.objects.get_by_tag_slug(tag.slug)
        if toggle_permission:
            toggle_permission.remove_users(list(superusers))


class Migration(migrations.Migration):

    dependencies = [
        ('toggles', '0001_toggle_edit_permission'),
    ]

    operations = [
        migrations.RunPython(
            _assign_all_toggle_edit_permissions_to_superusers,
            reverse_code=_reverse,
        ),
    ]
