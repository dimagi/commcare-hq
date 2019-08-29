
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockstate',
            name='last_modified_form_id',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
    ]
