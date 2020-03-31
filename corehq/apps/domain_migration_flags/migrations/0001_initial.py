from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DomainMigrationProgress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(default=None, max_length=256)),
                ('migration_slug', models.CharField(default=None, max_length=256)),
                ('migration_status', models.CharField(default='not_started', max_length=11, choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('complete', 'Complete')])),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='domainmigrationprogress',
            unique_together=set([('domain', 'migration_slug')]),
        ),
    ]
