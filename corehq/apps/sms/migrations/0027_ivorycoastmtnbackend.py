# Generated by Django 1.11.7 on 2017-11-15 12:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0026_add_messagingsubevent_case_id_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='IvoryCoastMTNBackend',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('sms.sqlsmsbackend',),
        ),
    ]
