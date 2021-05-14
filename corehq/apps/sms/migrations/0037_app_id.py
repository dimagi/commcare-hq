from django.db import migrations, models

from corehq.util.django_migrations import run_once_off_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0036_index_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='keywordaction',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='messagingevent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='messagingsubevent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        run_once_off_migration(
            'populate_app_id_for_sms', required_commit='ddb2c1e9ae4ea932dfa5e590e65aa74ed95ebf13'
        )
    ]
