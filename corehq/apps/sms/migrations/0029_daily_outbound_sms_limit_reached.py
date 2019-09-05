# Generated by Django 1.11.8 on 2018-02-02 12:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0028_messagingevent_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyOutboundSMSLimitReached',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=126)),
                ('date', models.DateField()),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='dailyoutboundsmslimitreached',
            unique_together=set([('domain', 'date')]),
        ),
    ]
