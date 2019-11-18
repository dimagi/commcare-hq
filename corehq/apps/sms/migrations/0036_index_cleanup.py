from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0034_auto_20191007_0756_noop'),
    ]

    operations = [
        migrations.RunSQL("DROP INDEX IF EXISTS {}".format(index), migrations.RunSQL.noop)
        for index in [
            'sms_messagingevent_recipient_id_402185bd326aa202_like',
            'sms_messagingsubevent_case_id_9cdc4e93_like',
            'sms_messagingevent_domain_4c2ba7e6c83c070f_like',
            'sms_messagingevent_recipient_type_562172ed7a8860b3_like',
            'sms_phonenumber_couch_id_3225a863d97086b_like',
            'sms_sms_couch_recipient_eb33f8f3c31578a_like',
        ]
    ]
