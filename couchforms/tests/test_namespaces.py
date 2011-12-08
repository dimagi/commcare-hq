import os
from datetime import date
from django.conf import settings
from django.test import TestCase
from dimagi.utils.post import post_authenticated_data
from couchforms.models import XFormInstance

class TestNamespaces(TestCase):
    
    def testClosed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "namespaces.xml")
        xml_data = open(file_path, "rb").read()
        doc_id, errors = post_authenticated_data(xml_data, 
                                                 settings.XFORMS_POST_URL, 
                                                 settings.COUCH_USERNAME,
                                                 settings.COUCH_PASSWORD)
        xform = XFormInstance.get(doc_id)
        self.assertEqual("http://commcarehq.org/test/ns", xform.xmlns)
        self.assertEqual("no namespace here", xform.xpath("form/empty"))
        self.assertEqual("http://commcarehq.org/test/flatns", xform.xpath("form/flat")["@xmlns"])
        self.assertEqual("http://commcarehq.org/test/parent", xform.xpath("form/parent")["@xmlns"])
        self.assertEqual("cwo", xform.xpath("form/parent/childwithout"))
        self.assertEqual("http://commcarehq.org/test/child1", xform.xpath("form/parent/childwith")["@xmlns"])
        self.assertEqual("http://commcarehq.org/test/child2", xform.xpath("form/parent/childwithelement")["@xmlns"])
        self.assertEqual("gc", xform.xpath("form/parent/childwithelement/grandchild"))
        self.assertEqual("lcwo", xform.xpath("form/parent/lastchildwithout"))
        self.assertEqual("nothing here either", xform.xpath("form/lastempty"))
        