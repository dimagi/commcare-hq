# Generated by Django 4.2.16 on 2025-03-21 17:26

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="IPAccessConfig",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("domain", models.CharField(unique=True, db_index=True, max_length=126)),
                (
                    "country_allowlist",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=2),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "ip_allowlist",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.GenericIPAddressField(),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "ip_denylist",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.GenericIPAddressField(),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("comment", models.TextField(blank=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
