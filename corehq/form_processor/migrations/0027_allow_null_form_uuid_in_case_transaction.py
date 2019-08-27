
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0026_caseforms_to_casetransaction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='form_uuid',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
