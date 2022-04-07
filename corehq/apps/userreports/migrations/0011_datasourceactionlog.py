# Generated by Django 1.11.20 on 2019-04-05 15:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0010_add_invaliducrdata'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSourceActionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('indicator_config_id', models.CharField(db_index=True, max_length=126)),
                ('initiated_by', models.CharField(max_length=126, null=True, blank=True)),
                ('action_source', models.CharField(db_index=True, null=True, max_length=126)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(choices=[('build', 'Build'), ('migrate', 'Migrate'), ('rebuild', 'Rebuild'), ('drop', 'Drop')], db_index=True, max_length=32)),
                ('migration_diffs', models.JSONField(null=True, blank=True)),
            ],
        ),
    ]
