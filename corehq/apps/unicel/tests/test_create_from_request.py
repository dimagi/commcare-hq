from datetime import datetime
from django.test import TestCase
from corehq.apps.unicel.api import InboundParams

class IncomingPostTest(TestCase):

    def SetUp(self):
        self.user = 'username'
        self.password = 'password'
        self.domain = 'mockdomain'
        self.phone_number = '5555551234'
        self.message = 'Test Message'
        self.couch_user = WebUser.create(self.domain, self.username, self.password);
        self.couch_user.save()


    def testPostToIncoming(self):
        fake_post = {InboundParams.SENDER: self.phone_number,
                     InboundParams.MESSAGE: self.message,
                     InboundParams.TIMESTAMP: datetime.now()}