import jsonfield
from corehq.messaging.scheduling.models.abstract import Content


class SMSContent(Content):
    message = jsonfield.JSONField(default=dict)

    def send(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'Message: ', self.message
        print '*******************************'
