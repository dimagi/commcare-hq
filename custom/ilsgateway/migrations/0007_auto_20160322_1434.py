# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
        ('ilsgateway', '0006_delete_supply_point_warehouse_record'),
    ]

    operations = [
        migrations.CreateModel(
            name='SLABConfig',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_pilot', models.BooleanField(default=False)),
                ('closest_supply_points', models.ManyToManyField(related_name='+', to='locations.SQLLocation')),
                ('sql_location', models.ForeignKey(to='locations.SQLLocation', unique=True, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
