# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocTypeMigrationCheckpoint',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('seq', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RenameModel(
            old_name='DocTypeMigrationState',
            new_name='DocTypeMigration',
        ),
        migrations.AddField(
            model_name='doctypemigrationcheckpoint',
            name='migration',
            field=models.ForeignKey(to='doctypemigrations.DocTypeMigration'),
            preserve_default=True,
        ),
    ]
