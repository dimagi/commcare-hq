
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0004_caseuploadrecord_case_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseUploadFileMeta',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('identifier', models.CharField(unique=True, max_length=256)),
                ('filename', models.CharField(max_length=256)),
                ('length', models.IntegerField()),
            ],
        ),
    ]
