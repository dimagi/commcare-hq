
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0028_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='opened_by',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='opened_on',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
