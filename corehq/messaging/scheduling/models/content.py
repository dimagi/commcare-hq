import jsonfield
from corehq.messaging.scheduling.models.abstract import Content
from django.db import models


class SMSContent(Content):
    message = jsonfield.JSONField(default=dict)

    def send(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'Message: ', self.message
        print '*******************************'


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
