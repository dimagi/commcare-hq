from django.db import migrations


VALID_TAG_SLUGS = [
    "release",
    "ga_path",
    "frozen",
    "deprecated",
    "solutions_internal",
]


def _sync_toggle_edit_permissions(apps, schema_editor):
    ToggleEditPermission = apps.get_model("toggles", "ToggleEditPermission")
    ToggleEditPermission.objects.exclude(tag_slug__in=VALID_TAG_SLUGS).delete()

    existing = set(
        ToggleEditPermission.objects.filter(tag_slug__in=VALID_TAG_SLUGS)
        .values_list("tag_slug", flat=True)
    )
    to_create = [
        ToggleEditPermission(tag_slug=tag_slug, enabled_users=[])
        for tag_slug in VALID_TAG_SLUGS
        if tag_slug not in existing
    ]
    if to_create:
        ToggleEditPermission.objects.bulk_create(to_create)


class Migration(migrations.Migration):

    dependencies = [
        ("toggles", "0006_alter_toggleeditpermission_tag_slug"),
    ]

    operations = [
        migrations.RunPython(
            _sync_toggle_edit_permissions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
