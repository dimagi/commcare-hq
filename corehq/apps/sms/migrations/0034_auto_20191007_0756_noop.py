from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0033_starfishbackend'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagingevent',
            name='content_type',
            field=models.CharField(choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email')], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingevent',
            name='recipient_type',
            field=models.CharField(choices=[('CAS', 'Case'), ('MOB', 'Mobile Worker'), ('WEB', 'Web User'), ('UGP', 'User Group'), ('CGP', 'Case Group'), ('MUL', 'Multiple Recipients'), ('LOC', 'Location'), ('LC+', 'Location (including child locations)'), ('VLC', 'Multiple Locations'), ('VL+', 'Multiple Locations (including child locations)'), ('UNK', 'Unknown Contact')], db_index=True, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='messagingevent',
            name='status',
            field=models.CharField(choices=[('PRG', 'In Progress'), ('CMP', 'Completed'), ('NOT', 'Not Completed'), ('ERR', 'Error')], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingsubevent',
            name='content_type',
            field=models.CharField(choices=[('NOP', 'None'), ('SMS', 'SMS Message'), ('CBK', 'SMS Expecting Callback'), ('SVY', 'SMS Survey'), ('IVR', 'IVR Survey'), ('VER', 'Phone Verification'), ('ADH', 'Manually Sent Message'), ('API', 'Message Sent Via API'), ('CHT', 'Message Sent Via Chat'), ('EML', 'Email')], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingsubevent',
            name='recipient_type',
            field=models.CharField(choices=[('CAS', 'Case'), ('MOB', 'Mobile Worker'), ('WEB', 'Web User')], max_length=3),
        ),
        migrations.AlterField(
            model_name='messagingsubevent',
            name='status',
            field=models.CharField(choices=[('PRG', 'In Progress'), ('CMP', 'Completed'), ('NOT', 'Not Completed'), ('ERR', 'Error')], max_length=3),
        ),
        migrations.AlterField(
            model_name='selfregistrationinvitation',
            name='phone_type',
            field=models.CharField(choices=[('android', 'Android'), ('other', 'Other')], max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='sqlmobilebackend',
            name='backend_type',
            field=models.CharField(choices=[('SMS', 'SMS'), ('IVR', 'IVR')], default='SMS', max_length=3),
        ),
        migrations.AlterField(
            model_name='sqlmobilebackendmapping',
            name='backend_type',
            field=models.CharField(choices=[('SMS', 'SMS'), ('IVR', 'IVR')], max_length=3),
        ),
    ]
