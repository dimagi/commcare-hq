
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseuploadrecord',
            name='task_id',
            field=models.UUIDField(unique=True),
        ),
        migrations.AlterField(
            model_name='caseuploadrecord',
            name='upload_id',
            field=models.UUIDField(unique=True),
        ),
    ]
