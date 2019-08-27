
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0005_caseuploadfilemeta'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseuploadrecord',
            name='upload_file_meta',
            field=models.ForeignKey(to='case_importer.CaseUploadFileMeta', null=True, on_delete=models.CASCADE),
        ),
    ]
