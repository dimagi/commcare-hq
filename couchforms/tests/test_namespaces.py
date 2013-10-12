import os
from django.test import TestCase
from couchforms import create_xform_from_xml
from couchforms.models import XFormInstance


class TestNamespaces(TestCase):
    
    def testClosed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "namespaces.xml")
        xml_data = open(file_path, "rb").read()
        doc_id = create_xform_from_xml(xml_data)
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
