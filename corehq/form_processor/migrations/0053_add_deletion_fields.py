from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0052_auto_20160224_1011'),
    ]

    operations = [
        migrations.AddField(
            model_name='commcarecasesql',
            name='deleted_on',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='commcarecasesql',
            name='deletion_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='deleted_on',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='deletion_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
