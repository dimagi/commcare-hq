# Generated by Django 1.10.6 on 2017-03-21 20:19

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('userreports', '0002_migrate_translation_transforms'),
    ]

    operations = [
        migrations.CreateModel(
            name='AsyncIndicator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_id', models.CharField(db_index=True, max_length=255)),
                ('doc_type', models.CharField(max_length=126)),
                ('domain', models.CharField(max_length=126)),
                ('pillow', models.CharField(max_length=126)),
                ('indicator_config_ids', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=126, null=True), size=None)),
                ('date_created', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'ordering': ['date_created'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='asyncindicator',
            unique_together=set([('doc_id', 'pillow')]),
        ),
    ]
