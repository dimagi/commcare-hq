# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0016_remove_billingcontactinfo_emails'),
    ]

    operations = [
        migrations.AddField(
            model_name='softwareplanversion',
            name='product_rate',
            field=models.ForeignKey(to='accounting.SoftwareProductRate', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='softwareplanversion',
            name='product_rates',
            field=models.ManyToManyField(related_name='+', to='accounting.SoftwareProductRate', blank=True),
            preserve_default=True,
        ),
    ]
