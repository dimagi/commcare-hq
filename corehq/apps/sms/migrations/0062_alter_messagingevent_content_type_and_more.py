# Generated by Django 4.2.15 on 2024-11-28 01:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0061_connectmessage_message_id_connectmessage_received_on'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagingevent',
            name='content_type',
            field=models.CharField(choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email'), ('FCM', 'FCM Push Notification'), ('CON', 'Connect Message'), ('CSY', 'Connect Message Survey')], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingsubevent',
            name='content_type',
            field=models.CharField(choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email'), ('FCM', 'FCM Push Notification'), ('CON', 'Connect Message'), ('CSY', 'Connect Message Survey')], max_length=3),
        ),
    ]