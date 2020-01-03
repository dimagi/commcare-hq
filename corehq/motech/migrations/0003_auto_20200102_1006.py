from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0002_requestlog_payload_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requestlog',
            name='payload_id',
            field=models.CharField(blank=True, db_index=True, max_length=126, null=True),
        ),
        migrations.AlterField(
            model_name='requestlog',
            name='request_url',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='requestlog',
            name='response_status',
            field=models.IntegerField(db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='requestlog',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
