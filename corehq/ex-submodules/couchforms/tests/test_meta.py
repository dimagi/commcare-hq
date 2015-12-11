from decimal import Decimal
import os
from datetime import date, datetime
from django.test import TestCase
from django.conf import settings

from corehq.util.test_utils import TestFileMixin
from couchforms.datatypes import GeoPoint
from couchforms.models import XFormInstance

from corehq.form_processor.tests.utils import run_with_all_backends, post_xform


class TestMeta(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)
    maxDiff = None

    def tearDown(self):
        XFormInstance.get_db().flush()

    def _check_metadata(self, xform, expected):
        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            del expected['doc_type']
            del expected['deprecatedID']
        self.assertEqual(xform.metadata.to_json(), expected)

    @run_with_all_backends
    def testClosed(self):
        xml_data = self.get_xml('meta')
        xform = post_xform(xml_data)

        self.assertNotEqual(None, xform.metadata)
        self.assertEqual(date(2010, 07, 22), xform.metadata.timeStart.date())
        self.assertEqual(date(2010, 07, 23), xform.metadata.timeEnd.date())
        self.assertEqual("admin", xform.metadata.username)
        self.assertEqual("f7f0c79e-8b79-11df-b7de-005056c00008", xform.metadata.userID)
        self.assertEqual("v1.2.3 (biz bazzle)", xform.metadata.appVersion)
        result = {
            'username': u'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11.648000Z',
            'appVersion': u'v1.2.3 (biz bazzle)',
            'timeStart': '2010-07-22T13:54:27.971000Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': u'5020280',
            'location': None,
        }
        self._check_metadata(xform, result)

    @run_with_all_backends
    def testDecimalAppVersion(self):
        '''
        Tests that an appVersion that looks like a decimal:
        (a) is not converted to a Decimal by couchdbkit
        (b) does not crash anything
        '''
        xml_data = self.get_xml('decimalmeta')
        xform = post_xform(xml_data)

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': u'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11.648000Z',
            'appVersion': u'2.0',
            'timeStart': '2010-07-22T13:54:27.971000Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': u'5020280',
            'location': None,
        }
        self._check_metadata(xform, result)

    @run_with_all_backends
    def testMetaBadUsername(self):
        xml_data = self.get_xml('meta_bad_username')
        xform = post_xform(xml_data)

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': u'2013-07-19',
            'doc_type': 'Metadata',
            'instanceID': u'e8afaec3c66745ef80e48062d4b91b56',
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': u'2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': u'commconnect',
            'location': None,
        }
        self._check_metadata(xform, result)

    @run_with_all_backends
    def testMetaAppVersionDict(self):
        xml_data = self.get_xml('meta_dict_appversion')
        xform = post_xform(xml_data)

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': u'some_username@test.commcarehq.org',
            'doc_type': 'Metadata',
            'instanceID': u'5d3d01561f584e85b53669a48bfc6039',
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': u'2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': u'commconnect',
            'location': None,
        }
        self._check_metadata(xform, result)

    @run_with_all_backends
    def test_gps_location(self):
        xml_data = self.get_xml('gps_location', override_path=('data',))

        xform = post_xform(xml_data)

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

        result = {
            'username': u'some_username@test.commcarehq.org',
            'doc_type': 'Metadata',
            'instanceID': u'5d3d01561f584e85b53669a48bfc6039',
            'userID': u'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': u'2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': u'commconnect',
            'location': '42.3739063 -71.1109113 0.0 886.0',
        }
        self._check_metadata(xform, result)

    @run_with_all_backends
    def test_empty_gps_location(self):
        xml_data = self.get_xml('gps_empty_location', override_path=('data',))
        xform = post_xform(xml_data)

        self.assertEqual(
            xform.metadata.location,
            None
        )

        self.assertEqual(xform.metadata.to_json()['location'], None)

    @run_with_all_backends
    def testMetaDateInDatetimeFields(self):
        xml_data = self.get_xml('date_in_meta', override_path=('data',))
        xform = post_xform(xml_data)

        self.assertEqual(datetime(2014, 7, 10), xform.metadata.timeStart)
        self.assertEqual(datetime(2014, 7, 11), xform.metadata.timeEnd)

    @run_with_all_backends
    def test_missing_meta_key(self):
        xml_data = self.get_xml('missing_date_in_meta', override_path=('data',))
        xform = post_xform(xml_data)
        self.assertEqual(datetime(2014, 7, 10), xform.metadata.timeStart)
        self.assertIsNone(xform.metadata.timeEnd)
