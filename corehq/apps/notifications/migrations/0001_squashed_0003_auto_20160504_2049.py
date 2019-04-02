# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    replaces = [('notifications', '0001_initial'), ('notifications', '0002_auto_20160504_1904'), ('notifications', '0003_auto_20160504_2049')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('content', models.CharField(max_length=140)),
                ('url', models.URLField()),
                ('type', models.CharField(max_length=10, choices=[(b'info', b'info'), (b'alert', b'alert')])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('users_read', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='notification',
            options={'ordering': ['-created']},
        ),
        migrations.AddField(
            model_name='notification',
            name='is_active',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='notification',
            name='created',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
            preserve_default=True,
        ),
    ]
