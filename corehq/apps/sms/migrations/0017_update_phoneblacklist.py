# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0016_add_phonenumber'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.AddField(
            model_name='phoneblacklist',
            name='domain',
            field=models.CharField(max_length=126, null=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='phoneblacklist',
            name='last_sms_opt_in_timestamp',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='phoneblacklist',
            name='last_sms_opt_out_timestamp',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
