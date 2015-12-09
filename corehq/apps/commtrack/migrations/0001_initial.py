# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('section_id', models.CharField(max_length=100, db_index=True)),
                ('case_id', models.CharField(max_length=100, db_index=True)),
                ('product_id', models.CharField(max_length=100, db_index=True)),
                ('stock_on_hand', models.DecimalField(default=Decimal('0'), max_digits=20, decimal_places=5)),
                ('daily_consumption', models.DecimalField(null=True, max_digits=20, decimal_places=5)),
                ('last_modified_date', models.DateTimeField()),
                ('sql_location', models.ForeignKey(to='locations.SQLLocation', null=True)),
                ('sql_product', models.ForeignKey(to='products.SQLProduct')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='stockstate',
            unique_together=set([('section_id', 'case_id', 'product_id')]),
        ),
    ]
