from decimal import Decimal
import os
from datetime import date, datetime
from django.test import TestCase
from couchforms.tests.testutils import create_and_save_xform
from couchforms.datatypes import GeoPoint
from couchforms.models import XFormInstance


class TestMeta(TestCase):
    
    def testClosed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
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
            'clinic_id': u'5020280',
            'location': None,
        })

    def testDecimalAppVersion(self):
        '''
        Tests that an appVersion that looks like a decimal:
        (a) is not converted to a Decimal by couchdbkit
        (b) does not crash anything
        '''
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "decimalmeta.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
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
            'location': None,
        })

    def testMetaBadUsername(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta_bad_username.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
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
                'deviceID': u'commconnect',
                'location': None,
            })
            xform.delete()

    def testMetaAppVersionDict(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta_dict_appversion.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
            xform = XFormInstance.get(doc_id)
            self.assertEqual(xform.metadata.appVersion, '2.0')

            self.assertEqual(xform.metadata.to_json(), {
                'username': u'some_username@test.commcarehq.org',
                'doc_type': 'Metadata',
                'instanceID': u'5d3d01561f584e85b53669a48bfc6039',
                'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
                'timeEnd': '2013-07-20T00:02:27Z',
                'appVersion': u'2.0',
                'timeStart': '2013-07-19T21:21:31Z',
                'deprecatedID': None,
                'deviceID': u'commconnect',
                'location': None,
            })
            xform.delete()

    def test_gps_location(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "gps_location.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
            xform = XFormInstance.get(doc_id)
            self.assertEqual(
                xform.metadata.location,
                # '42.3739063 -71.1109113 0.0 886.0'
                GeoPoint(
                    latitude=Decimal('42.3739063'),
                    longitude=Decimal('-71.1109113'),
                    altitude=Decimal('0.0'),
                    accuracy=Decimal('886.0'),
                )
            )

            self.assertEqual(xform.metadata.to_json(), {
                'username': u'some_username@test.commcarehq.org',
                'doc_type': 'Metadata',
                'instanceID': u'5d3d01561f584e85b53669a48bfc6039',
                'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
                'timeEnd': '2013-07-20T00:02:27Z',
                'appVersion': u'2.0',
                'timeStart': '2013-07-19T21:21:31Z',
                'deprecatedID': None,
                'deviceID': u'commconnect',
                'location': '42.3739063 -71.1109113 0.0 886.0',
            })
            xform.delete()

    def test_empty_gps_location(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "gps_empty_location.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
            xform = XFormInstance.get(doc_id)
            self.assertEqual(
                xform.metadata.location,
                None
            )

            self.assertEqual(xform.metadata.to_json()['location'], None)
            xform.delete()

    def testMetaDateInDatetimeFields(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "date_in_meta.xml")
        xml_data = open(file_path, "rb").read()
        with create_and_save_xform(xml_data) as doc_id:
            xform = XFormInstance.get(doc_id)
            self.assertEqual(datetime(2014, 7, 10), xform.metadata.timeStart)
            self.assertEqual(datetime(2014, 7, 11), xform.metadata.timeEnd)
            xform.delete()
