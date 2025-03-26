import uuid

from django.db import migrations, models

import jsonfield.fields
from architect.commands import partition

import corehq.sql_db.fields


def add_partitions(apps, schema_editor):
    partition.run({'module': 'corehq.motech.repeaters.models'})


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0017_add_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataSourceUpdateLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_column="id_",
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "domain",
                    corehq.sql_db.fields.CharIdField(db_index=True, max_length=126),
                ),
                ("data_source_id", models.UUIDField()),
                ("doc_ids", jsonfield.fields.JSONField(default=list)),
                (
                    "rows",
                    jsonfield.fields.JSONField(blank=True, default=list, null=True),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "repeaters_datasourceupdatelog",
            },
        ),
        migrations.RunPython(add_partitions),
    ]
