from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0048_delete_sqlicdsbackend'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLTestSMSWithAPIBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
    ]
