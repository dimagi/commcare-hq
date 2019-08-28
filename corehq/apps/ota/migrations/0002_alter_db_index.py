
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ota', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='demouserrestore',
            name='demo_user_id',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
    ]
