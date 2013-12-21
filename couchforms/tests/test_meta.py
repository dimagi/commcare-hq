import os
from datetime import date
from django.test import TestCase
from couchforms import create_xform_from_xml
from couchforms.models import XFormInstance


class TestMeta(TestCase):
    
    def testClosed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()
        doc_id = create_xform_from_xml(xml_data)
        xform = XFormInstance.get(doc_id)
        self.assertNotEqual(None, xform.metadata)
        self.assertEqual(date(2010,07,22), xform.metadata.timeStart.date())
        self.assertEqual(date(2010,07,23), xform.metadata.timeEnd.date())
        self.assertEqual("admin", xform.metadata.username)
        self.assertEqual("f7f0c79e-8b79-11df-b7de-005056c00008", xform.metadata.userID)
        self.assertEqual("v1.2.3 (biz bazzle)", xform.metadata.appVersion)
        self.assertEqual(xform.metadata.to_json(), {
            'username': u'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11Z',
            'appVersion': u'v1.2.3 (biz bazzle)',
            'timeStart': '2010-07-22T13:54:27Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': u'5020280'
        })
        
    def testDecimalAppVersion(self):
        '''
        Tests that an appVersion that looks like a decimal:
        (a) is not converted to a Decimal by couchdbkit
        (b) does not crash anything
        '''
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "decimalmeta.xml")
        xml_data = open(file_path, "rb").read()
        doc_id = create_xform_from_xml(xml_data)
        xform = XFormInstance.get(doc_id)
        self.assertEqual(xform.metadata.appVersion, '2.0')
        self.assertEqual(xform.metadata.to_json(), {
            'username': u'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11Z',
            'appVersion': u'2.0',
            'timeStart': '2010-07-22T13:54:27Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': u'5020280',
        })

    def testMetaBadUsername(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta_bad_username.xml")
        xml_data = open(file_path, "rb").read()
        doc_id = create_xform_from_xml(xml_data)
        xform = XFormInstance.get(doc_id)
        self.assertEqual(xform.metadata.appVersion, '2.0')

        self.assertEqual(xform.metadata.to_json(), {
            'username': u'2013-07-19',
            'doc_type': 'Metadata',
            'instanceID': u'e8afaec3c66745ef80e48062d4b91b56',
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27Z',
            'appVersion': u'2.0',
            'timeStart': '2013-07-19T21:21:31Z',
            'deprecatedID': None,
            'deviceID': u'commconnect'
        })
        xform.delete()

    def testMetaAppVersionDict(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta_dict_appversion.xml")
        xml_data = open(file_path, "rb").read()
        doc_id = create_xform_from_xml(xml_data)
        xform = XFormInstance.get(doc_id)
        self.assertEqual(xform.metadata.appVersion, '2.0')

        j = xform.metadata.to_json()
        self.assertEqual(xform.metadata.to_json(), {
            'username': u'some_username@test.commcarehq.org',
            'doc_type': 'Metadata',
            'instanceID': u'5d3d01561f584e85b53669a48bfc6039',
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27Z',
            'appVersion': u'2.0',
            'timeStart': '2013-07-19T21:21:31Z',
            'deprecatedID': None,
            'deviceID': u'commconnect'
        })
        xform.delete()
