
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0004_optional_modified_date_and_prop_type_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automaticupdaterulecriteria',
            name='match_type',
            field=models.CharField(max_length=15),
        ),
    ]
