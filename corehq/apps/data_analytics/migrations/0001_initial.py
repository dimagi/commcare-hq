# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MALTRow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('month', models.DateField(db_index=True)),
                ('user_id', models.TextField()),
                ('username', models.TextField()),
                ('email', models.EmailField(max_length=75)),
                ('is_web_user', models.BooleanField(default=False)),
                ('domain_name', models.TextField(db_index=True)),
                ('num_of_forms', models.PositiveIntegerField()),
                ('app_id', models.TextField()),
                ('is_app_deleted', models.BooleanField(default=False)),
                ('wam', models.NullBooleanField(default=None)),
                ('pam', models.NullBooleanField(default=None)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='maltrow',
            unique_together=set([('month', 'domain_name', 'user_id', 'app_id')]),
        ),
    ]
