from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0072_case_attachment_drops'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='_client_date',
            field=models.DateTimeField(db_column='client_date', null=True),
        ),
    ]
