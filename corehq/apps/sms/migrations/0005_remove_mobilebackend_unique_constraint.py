# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0004_add_sqlivrbackend_sqlkookoobackend'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='sqlmobilebackend',
            unique_together=set([]),
        ),
    ]
