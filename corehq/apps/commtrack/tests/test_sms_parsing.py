from django.utils.unittest.case import TestCase
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.sms import StockReportParser, to_instance
from lxml import etree

class SMSParseTest(CommTrackTest):
    requisitions_enabled = True

    def testThing(self):
        data = StockReportParser(self.domain, self.user.get_verified_number()).parse(
            'req loc1 pp 10 pq 20 pr 30'
        )
        xml = etree.to_string(to_instance(data))
