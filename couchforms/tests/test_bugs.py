import os
from django.test import TestCase
from couchforms.util import post_xform_to_couch
import uuid

class CloudantTest(TestCase):

    def testCloudantRaceCondition(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "cloudant-template.xml")
        with open(file_path) as f:
            xml_data = f.read()

        count = 1000
        for i in range(count):
            instance_id = uuid.uuid4().hex
            case_id = uuid.uuid4().hex
            xform = post_xform_to_couch(xml_data.format(
                instance_id=instance_id,
                case_id=case_id,
            ))
            xform.foo = 'bar'
            xform.save()
            print '%s/%s ok' % (i, count)
