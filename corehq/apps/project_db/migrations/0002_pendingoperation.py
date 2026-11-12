from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project_db', '0001_setup_projectdb'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingOperation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('operation', models.CharField(choices=[('sync', 'Sync'), ('backfill', 'Backfill')], max_length=32)),
                ('args', models.JSONField(default=dict)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
