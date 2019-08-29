
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0011_date_to_datetime'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsgatewayfeecriteria',
            name='country_code',
            field=models.IntegerField(db_index=True, null=True, blank=True),
            preserve_default=True,
        ),
    ]
