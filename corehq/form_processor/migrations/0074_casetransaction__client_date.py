
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0073_drop_case_uuid_like_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='_client_date',
            field=models.DateTimeField(db_column='client_date', null=True),
        ),
    ]
