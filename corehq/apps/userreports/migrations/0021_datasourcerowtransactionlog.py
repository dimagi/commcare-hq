# Generated by Django 3.2.23 on 2023-11-16 13:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0020_delete_ucr_comparison_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSourceRowTransactionLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(choices=[('upsert', 'upsert'), ('delete', 'delete')], max_length=32)),
                ('data_source_id', models.CharField(db_index=True, max_length=255)),
                ('row_id', models.CharField(db_index=True, max_length=255)),
                ('row_data', models.JSONField(blank=True, null=True)),
            ],
        ),
    ]
