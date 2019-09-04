
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0006_remove_smsbillable_api_response'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsbillable',
            name='multipart_count',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
    ]
