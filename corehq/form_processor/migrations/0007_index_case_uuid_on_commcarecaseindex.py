
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0006_commcarecaseindexsql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(to='form_processor.CommCareCaseSQL', db_column='case_uuid', to_field='case_uuid', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
