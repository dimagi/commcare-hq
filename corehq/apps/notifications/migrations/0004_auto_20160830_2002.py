
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_lastseennotification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lastseennotification',
            name='user',
            field=models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
