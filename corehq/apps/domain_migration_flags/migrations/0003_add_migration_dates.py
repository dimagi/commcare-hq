# Generated by Django 1.11.20 on 2019-04-01 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain_migration_flags', '0002_migrate_data_from_tzmigration'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainmigrationprogress',
            name='completed_on',
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='domainmigrationprogress',
            name='started_on',
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='domainmigrationprogress',
            name='migration_status',
            field=models.CharField(choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('dry_run', 'Dry Run'), ('complete', 'Complete')], default='not_started', max_length=11),
        ),
    ]
