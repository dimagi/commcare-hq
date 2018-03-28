from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal
import os
from datetime import date, datetime
from django.test import TestCase
from django.conf import settings

from casexml.apps.case.tests.util import delete_all_xforms
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import TestFileMixin
from couchforms.datatypes import GeoPoint


class TestMeta(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)
    maxDiff = None

    def tearDown(self):
        delete_all_xforms()

    def _check_metadata(self, xform, expected):
        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            del expected['doc_type']
            del expected['deprecatedID']
        self.assertEqual(xform.metadata.to_json(), expected)

    def testClosed(self):
        xml_data = self.get_xml('meta')
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertNotEqual(None, xform.metadata)
        self.assertEqual(date(2010, 7, 22), xform.metadata.timeStart.date())
        self.assertEqual(date(2010, 7, 23), xform.metadata.timeEnd.date())
        self.assertEqual("admin", xform.metadata.username)
        self.assertEqual("f7f0c79e-8b79-11df-b7de-005056c00008", xform.metadata.userID)
        self.assertEqual("v1.2.3 (biz bazzle)", xform.metadata.appVersion)
        result = {
            'username': 'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': 'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11.648000Z',
            'appVersion': 'v1.2.3 (biz bazzle)',
            'timeStart': '2010-07-22T13:54:27.971000Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': '5020280',
            'location': None,
        }
        self._check_metadata(xform, result)

    def testDecimalAppVersion(self):
        '''
        Tests that an appVersion that looks like a decimal:
        (a) is not converted to a Decimal by couchdbkit
        (b) does not crash anything
        '''
        xml_data = self.get_xml('decimalmeta')
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': 'admin',
            'doc_type': 'Metadata',
            'instanceID': None,
            'userID': 'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2010-07-23T13:55:11.648000Z',
            'appVersion': '2.0',
            'timeStart': '2010-07-22T13:54:27.971000Z',
            'deprecatedID': None,
            'deviceID': None,
            'clinic_id': '5020280',
            'location': None,
        }
        self._check_metadata(xform, result)

    def testMetaBadUsername(self):
        xml_data = self.get_xml('meta_bad_username')
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': '2013-07-19',
            'doc_type': 'Metadata',
            'instanceID': 'e8afaec3c66745ef80e48062d4b91b56',
            'userID': 'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': '2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': 'commconnect',
            'location': None,
        }
        self._check_metadata(xform, result)

    def testMetaAppVersionDict(self):
        xml_data = self.get_xml('meta_dict_appversion')
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual(xform.metadata.appVersion, '2.0')
        result = {
            'username': 'some_username@test.commcarehq.org',
            'doc_type': 'Metadata',
            'instanceID': '5d3d01561f584e85b53669a48bfc6039',
            'userID': 'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': '2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': 'commconnect',
            'location': None,
        }
        self._check_metadata(xform, result)

    def test_gps_location(self):
        xml_data = self.get_xml('gps_location', override_path=('data',))

        xform = submit_form_locally(xml_data, 'test-domain').xform

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
            'username': 'some_username@test.commcarehq.org',
            'doc_type': 'Metadata',
            'instanceID': '5d3d01561f584e85b53669a48bfc6039',
            'userID': 'f7f0c79e-8b79-11df-b7de-005056c00008',
            'timeEnd': '2013-07-20T00:02:27.493000Z',
            'appVersion': '2.0',
            'timeStart': '2013-07-19T21:21:31.188000Z',
            'deprecatedID': None,
            'deviceID': 'commconnect',
            'location': '42.3739063 -71.1109113 0.0 886.0',
        }
        self._check_metadata(xform, result)

    def test_empty_gps_location(self):
        xml_data = self.get_xml('gps_empty_location', override_path=('data',))
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual(
            xform.metadata.location,
            None
        )

        self.assertEqual(xform.metadata.to_json()['location'], None)

    def testMetaDateInDatetimeFields(self):
        xml_data = self.get_xml('date_in_meta', override_path=('data',))
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual(datetime(2014, 7, 10), xform.metadata.timeStart)
        self.assertEqual(datetime(2014, 7, 11), xform.metadata.timeEnd)

    def test_missing_meta_key(self):
        xml_data = self.get_xml('missing_date_in_meta', override_path=('data',))
        xform = submit_form_locally(xml_data, 'test-domain').xform
        self.assertEqual(datetime(2014, 7, 10), xform.metadata.timeStart)
        self.assertIsNone(xform.metadata.timeEnd)


@use_sql_backend
class TestMetaSQL(TestMeta):
    pass
