from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0041_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='InfobipBackend',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.CreateModel(
            name='PinpointBackend',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.AlterField(
            model_name='messagingevent',
            name='status',
            field=models.CharField(choices=[
                ('PRG', 'In Progress'),
                ('CMP', 'Completed'),
                ('NOT', 'Not Completed'),
                ('ERR', 'Error'),
                ('SND', 'Email Sent'),
                ('DEL', 'Email Delivered'),
            ], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingsubevent',
            name='status',
            field=models.CharField(choices=[
                ('PRG', 'In Progress'),
                ('CMP', 'Completed'),
                ('NOT', 'Not Completed'),
                ('ERR', 'Error'),
                ('SND', 'Email Sent'),
                ('DEL', 'Email Delivered'),
            ], max_length=3),
        ),
    ]
