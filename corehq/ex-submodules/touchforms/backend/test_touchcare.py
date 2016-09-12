from __future__ import with_statement
import unittest
import os

from setup import init_classpath
init_classpath()
import touchcare
import persistence
import datetime
from xcp import TouchcareInvalidXPath, TouchFormsUnauthorized
from org.javarosa.core.util.externalizable import PrototypeFactory
from org.javarosa.core.api import ClassNameHasher

CUR_DIR = os.path.dirname(__file__)


class TouchcareTest(unittest.TestCase):

    persistence.postgres_drop_sqlite = lambda x: 0
    persistence.postgres_set_sqlite = lambda x, y: 0
    persistence.postgres_lookup_last_modified_command = lambda x, y: datetime.datetime.utcnow()
    PrototypeFactory.setStaticHasher(ClassNameHasher())

    def setUp(self):
        self.restore = os.path.join(CUR_DIR, 'test_files/restores/simple_restore.xml')

        self.session_data = {
            'session_name': 'Village Healthe > Simple Form',
            'app_version': '2.0',
            'device_id': 'cloudcare',
            'user_id': '51cd680c0bd1c21bb5e63dab99748248',
            'additional_filters': {'footprint': True},
            'domain': 'willslearningproject',
            'host': 'http://localhost:8000',
            'user_data': {},
            'case_id_new_RegCase_0': '1c2e7c76f0c84eaea5b44bc7d1d3caf0',
            'app_id': '6a48b8838d06febeeabb28c8c9516ab6',
            'username': 'wspride-tc-2'
        }

    def test_filter_cases(self):
        filter_expr = "[case_name = 'case']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            uses_sqlite=True,
        )
        self.assertEqual(len(resp['cases']), 2)

    def test_filter_cases_two(self):
        filter_expr = "[case_name = 'derp']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            force_sync=False,
            uses_sqlite=True,
        )
        self.assertEqual(len(resp['cases']), 0)

    def test_filter_cases_3(self):
        filter_expr = "[case_name = 'case']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            force_sync=False,
            uses_sqlite=True,
        )
        self.assertEqual(len(resp['cases']), 2)


class TouchcareLedgerTest(unittest.TestCase):

    PrototypeFactory.setStaticHasher(ClassNameHasher())

    def setUp(self):
        self.restore = os.path.join(CUR_DIR, 'test_files/restores/ipm_restore.xml')
        self.session_data = {
            'session_name': 'Village Healthe > Simple Form',
            'app_version': '2.0',
            'device_id': 'cloudcare',
            'user_id': 'a8f5a98c4ce767c35b9132bc75eb225c',
            'additional_filters': {'footprint': True},
            'domain': 'willslearningproject',
            'host': 'http://localhost:8000',
            'user_data': {},
            'case_id_new_RegCase_0': '1c2e7c76f0c84eaea5b44bc7d1d3caf0',
            'app_id': '6a48b8838d06febeeabb28c8c9516ab6',
            'username': 'ipm-test-2'
        }

    def test_filter_cases(self):
        filter_expr = "[case_name = 'Napoli']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            uses_sqlite=True,
        )
        self.assertEqual(len(resp['cases']), 1)

    def test_filter_cases_two(self):
        filter_expr = "[case_name = 'derp']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            uses_sqlite=True,
        )
        self.assertEqual(len(resp['cases']), 0)


class SubmissionTest(unittest.TestCase):

    def setUp(self):
        super(SubmissionTest, self).setUp()
        self.form = os.path.join(CUR_DIR, 'test_files/simple_submission.xml')
        self.restore = os.path.join(CUR_DIR, 'test_files/restores/simple_restore.xml')

        self.session_data = {
            'session_name': 'Village Healthe > Simple Form',
            'app_version': '2.0',
            'device_id': 'cloudcare',
            'user_id': '51cd680c0bd1c21bb5e63dab99748248',
            'additional_filters': {'footprint': True},
            'domain': 'willslearningproject',
            'host': 'http://localhost:8000',
            'user_data': {},
            'case_id_new_RegCase_0': '1c2e7c76f0c84eaea5b44bc7d1d3caf0',
            'app_id': '6a48b8838d06febeeabb28c8c9516ab6',
            'username': 'submission-test'
        }

        self.filter_expr = "[case_name = 'Napoli']"


class ParentClosedTests(unittest.TestCase):

    PrototypeFactory.setStaticHasher(ClassNameHasher())

    def setUp(self):
        self.restore = os.path.join(CUR_DIR, 'test_files/restores/icds_restore.xml')
        self.session_data = {
            'session_name': 'Whatever',
            'app_version': '2.0',
            'device_id': 'cloudcare',
            'user_id': 'a7514c522f36169e07555495acb9cffb',
            'additional_filters': {'footprint': True},
            'domain': 'icds-test',
            'host': 'http://localhost:8000',
            'user_data': {},
            'app_id': 'a7514c522f36169e07555495ac956bd4',
            'username': 'saket.district'
        }

    def test_filter_cases(self):
        filter_expr = "[@case_type='tech_issue']"

        resp = touchcare.filter_cases(
            filter_expr,
            {},
            self.session_data,
            restore_xml=self.restore,
            uses_sqlite=True,
        )

        self.assertEqual(len(resp['cases']), 2)

if __name__ == '__main__':
    unittest.main()
