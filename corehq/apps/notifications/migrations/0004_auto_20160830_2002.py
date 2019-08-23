# -*- coding: utf-8 -*-

from django.db import models, migrations
from django.conf import settings


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
