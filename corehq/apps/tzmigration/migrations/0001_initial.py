from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TimezoneMigrationProgress',
            fields=[
                ('domain', models.CharField(max_length=256, serialize=False, primary_key=True, db_index=True)),
                ('migration_status', models.CharField(default='not_started', max_length=11, choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('complete', 'Complete')])),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
