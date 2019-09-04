# Generated by Django 1.10.7 on 2017-04-14 19:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_auto_20170404_0028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriptionadjustment',
            name='method',
            field=models.CharField(choices=[(b'USER', b'User'), (b'INTERNAL', b'Ops'), (b'TASK', b'Task (Invoicing)'), (b'TRIAL', b'30 Day Trial'), (b'AUTOMATIC_DOWNGRADE', b'Automatic Downgrade')], default=b'INTERNAL', max_length=50),
        ),
    ]
