# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0026_subscriber_domain_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='defaultproductplan',
            name='edition',
            field=models.CharField(default=b'Community', max_length=25, choices=[(b'Community', b'Community'), (b'Standard', b'Standard'), (b'Pro', b'Pro'), (b'Advanced', b'Advanced'), (b'Enterprise', b'Enterprise'), (b'Reseller', b'Reseller'), (b'Managed Hosting', b'Managed Hosting')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='softwareplan',
            name='edition',
            field=models.CharField(default=b'Enterprise', max_length=25, choices=[(b'Community', b'Community'), (b'Standard', b'Standard'), (b'Pro', b'Pro'), (b'Advanced', b'Advanced'), (b'Enterprise', b'Enterprise'), (b'Reseller', b'Reseller'), (b'Managed Hosting', b'Managed Hosting')]),
            preserve_default=True,
        ),
    ]
