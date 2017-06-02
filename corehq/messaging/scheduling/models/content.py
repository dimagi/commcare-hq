import jsonfield
from corehq.apps.sms.api import send_sms_with_backend_name
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from django.db import models


class SMSContent(Content):
    message = jsonfield.JSONField(default=dict)

    def send(self, recipient):
        phone_number = get_one_way_number_for_recipient(recipient)
        if not phone_number or len(phone_number) <= 3:
            return

        language_code = recipient.get_language_code()
        message = self.message.get(language_code)
        if not message:
            message = self.message.get('en')

        if message:
            send_sms_with_backend_name(recipient.domain, phone_number, message, 'TEST')


class EmailContent(Content):
    subject = jsonfield.JSONField(default=dict)
    message = jsonfield.JSONField(default=dict)

    def send(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'Subject: ', self.subject
        print 'Message: ', self.message
        print '*******************************'


class SMSSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    # The number of minutes after which the survey expires
    expire_after = models.IntegerField()

    def send(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'SMS Survey: ', self.form_unique_id
        print '*******************************'


class IVRSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    def send(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'IVR Survey: ', self.form_unique_id
        print '*******************************'
