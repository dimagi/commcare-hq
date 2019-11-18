from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0060_convert_case_ids_to_foreign_keys'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseattachmentsql',
            name='blob_bucket',
            field=models.CharField(default=None, max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xformattachmentsql',
            name='blob_bucket',
            field=models.CharField(default=None, max_length=255, null=True),
            preserve_default=True,
        ),
    ]
