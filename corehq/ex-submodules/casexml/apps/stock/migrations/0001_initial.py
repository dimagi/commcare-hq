# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import casexml.apps.stock.models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocDomainMapping',
            fields=[
                ('doc_id', models.CharField(max_length=100, serialize=False, primary_key=True, db_index=True)),
                ('doc_type', models.CharField(max_length=100, db_index=True)),
                ('domain_name', models.CharField(max_length=100, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StockReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(max_length=100, db_index=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('type', models.CharField(max_length=20)),
                ('domain', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StockTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('section_id', models.CharField(max_length=100, db_index=True)),
                ('case_id', models.CharField(max_length=100, db_index=True)),
                ('product_id', models.CharField(max_length=100, db_index=True)),
                ('type', models.CharField(max_length=20)),
                ('subtype', casexml.apps.stock.models.TruncatingCharField(max_length=20, null=True, blank=True)),
                ('quantity', models.DecimalField(null=True, max_digits=20, decimal_places=5)),
                ('stock_on_hand', models.DecimalField(max_digits=20, decimal_places=5)),
                ('report', models.ForeignKey(to='stock.StockReport')),
                ('sql_product', models.ForeignKey(to='products.SQLProduct')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterIndexTogether(
            name='stocktransaction',
            index_together=set([('case_id', 'product_id', 'section_id')]),
        ),
    ]
