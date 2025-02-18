# Generated by Django 4.2.17 on 2025-02-12 00:46

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("export", "0013_rm_incrementalexport"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeIdMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("domain", models.TextField(max_length=255)),
                ("hashed_value", models.TextField(max_length=32)),
                ("deid", models.UUIDField(default=uuid.uuid4)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["domain", "hashed_value"],
                        name="export_deid_domain_3c63a4_idx",
                    )
                ],
            },
        ),
    ]
