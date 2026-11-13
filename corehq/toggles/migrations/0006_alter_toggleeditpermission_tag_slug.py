from django.db import migrations, models


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
        ("toggles", "0005_alter_toggleeditpermission_tag_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="toggleeditpermission",
            name="tag_slug",
            field=models.CharField(
                choices=[
                    ("release", "release"),
                    ("ga_path", "ga_path"),
                    ("frozen", "frozen"),
                    ("deprecated", "deprecated"),
                    ("solutions_internal", "solutions_internal"),
                ],
                max_length=255,
                unique=True,
            ),
        ),
        migrations.RunPython(
            _sync_toggle_edit_permissions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
