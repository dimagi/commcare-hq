# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0024_date_created_to_datetime'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditadjustment',
            name='invoice',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, to='accounting.Invoice', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditadjustment',
            name='line_item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, to='accounting.LineItem', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditadjustment',
            name='note',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditadjustment',
            name='payment_record',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, to='accounting.PaymentRecord', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditadjustment',
            name='related_credit',
            field=models.ForeignKey(related_name='creditadjustment_related', on_delete=django.db.models.deletion.PROTECT, blank=True, to='accounting.CreditLine', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creditadjustment',
            name='web_user',
            field=models.CharField(max_length=80, null=True, blank=True),
            preserve_default=True,
        ),
    ]
