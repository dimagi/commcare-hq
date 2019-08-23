# -*- coding: utf-8 -*-

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
        ('ilsgateway', '0004_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingReportingDataRecalculation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=128)),
                ('type', models.CharField(max_length=128)),
                ('data', jsonfield.fields.JSONField()),
                ('sql_location', models.ForeignKey(to='locations.SQLLocation', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        )
    ]
