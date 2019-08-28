
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0047_add_deleted_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseattachmentsql',
            name='blob_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='caseattachmentsql',
            name='content_length',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xformattachmentsql',
            name='blob_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='xformattachmentsql',
            name='content_length',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
    ]
