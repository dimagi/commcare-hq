from django.test import TestCase
import commands
from couchforms.models import XFormInstance
from datetime import datetime

#class SubmissionTest(TestCase):
#    def test_submission(self):
#        """
#        Submits an xml file to the server and test that it shows up
#        in couch
#        """
#        command = 'curl -X POST http://localhost:8000/demo/receiver/ -d @tmp.xml'
#        xmlns = 'axpoc8fasdlkfjas0d7fasdfas98dflsmda'
#
#        xml = """
#            <?xml version="1.0" encoding="ISO-8859-1" ?>
#            <root xmlns="%(xmlns)s" version="4" uiVersion="100">
#                <Meta>
#                    <formName>BlurkMorp</formName>
#                    <formVersion>0.0.1</formVersion>
#                    <chw_id>6</chw_id>
#                    <uid>ABCDEFGHIJKLMNOPQRSTUVWXYZ</uid>
#                    <DeviceID>ABCDEFGHIJKLMNOPQRSTUVWXYZ</DeviceID>
#                    <TimeStart>2007-01-30T11:11:20.961</TimeStart>
#                    <TimeEnd>2007-01-30T11:11:28.187</TimeEnd>
#                    <username>morkbert</username>
#                </Meta>
#                <nested>
#                  <my_user>userid0</my_user>
#                  <my_device>deviceid0</my_device>
#                  <TimeStartRecorded>2007-01-30T11:11:20.961</TimeStartRecorded>
#                  <TimeEndRecorded>2007-01-30T11:11:28.187</TimeEndRecorded>
#                </nested>
#                <nested>
#                  <my_user>userid2</my_user>
#                  <my_device>deviceid2</my_device>
#                  <TimeStartRecorded>2009-11-12T11:11:11</TimeStartRecorded>
#                  <TimeEndRecorded>2009-11-12T11:16:11</TimeEndRecorded>
#                </nested>
#                <LocFSSCother>foo</LocFSSCother>
#                <LocLPSCother>bar</LocLPSCother>
#                <LocMPSCother>yes</LocMPSCother>
#                <LocNCSCother>no</LocNCSCother>
#            </root>
#        """ % (locals())
#        tmpxml = 'tmp.xml'
#
#        with open(tmpxml, 'w') as f:
#            f.write(xml)
#        before = datetime.utcnow()
#        doc_id = commands.getoutput(command).split('\n')[-1]
#        after = datetime.utcnow()
#
#        commands.getoutput("rm %s" % tmpxml)
#
#        doc = XFormInstance.get(doc_id)
#        self.assertEqual(doc.xmlns, xmlns)
#        self.assertTrue(before < doc['received_on'] < after)
