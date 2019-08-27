
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0002_auto_20161206_1937'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseuploadrecord',
            name='couch_user_id',
            field=models.CharField(default='unknown', max_length=256),
            preserve_default=False,
        ),
    ]
