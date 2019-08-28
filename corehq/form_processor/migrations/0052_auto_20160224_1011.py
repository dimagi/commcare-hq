
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0051_auto_20160224_0922'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id', 'type')]),
        ),
    ]
