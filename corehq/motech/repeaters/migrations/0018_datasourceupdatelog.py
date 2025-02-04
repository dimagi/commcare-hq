import corehq.sql_db.fields
from django.db import migrations, models
import jsonfield.fields
import uuid


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
            ],
        ),
    ]
