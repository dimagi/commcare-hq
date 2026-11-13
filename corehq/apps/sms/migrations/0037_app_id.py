from django.db import migrations, models


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
    ]
