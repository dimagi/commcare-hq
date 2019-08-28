
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0005_add_forceclose_entry_20160408_1530'),
    ]

    operations = [
        migrations.AddField(
            model_name='usererrorentry',
            name='context_node',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
