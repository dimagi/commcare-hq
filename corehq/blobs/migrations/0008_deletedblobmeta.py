# Generated by Django 1.11.17 on 2019-01-14 16:51

from django.db import migrations, models

from corehq.sql_db.migrations import partitioned
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'blobs', 'sql_templates'), {})


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0007_drop_blobmeta_view'),
    ]

    operations = [
        partitioned(migrations.CreateModel(
            name='DeletedBlobMeta',
            fields=[
                ('id', models.IntegerField(primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('parent_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('key', models.CharField(max_length=255)),
                ('type_code', models.PositiveSmallIntegerField()),
                ('created_on', models.DateTimeField()),
                ('deleted_on', models.DateTimeField()),
            ],
            options={
                'abstract': False,
            },
        )),
        partitioned(
            migrator.get_migration('delete_blob_meta_v2.sql', 'delete_blob_meta.sql'),
            apply_to_proxy=False,
        ),
    ]
