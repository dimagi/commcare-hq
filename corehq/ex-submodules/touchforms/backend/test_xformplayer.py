import os
import unittest
import xformplayer
import touchcare

CUR_DIR = os.path.dirname(__file__)


class MockFunctionException(Exception):
    pass


class XFormPlayerTest(unittest.TestCase):

    def setUp(self):

        try:
            f = open(os.path.join(CUR_DIR, 'test_files/xforms/xform_simple_cases.xml'), 'r')
            self.xform = f.read()
        except IOError:
            self.fail('Could not read test form')

        self.session_data = {
            'session_name': 'Village Healthe > Simple Form',
            'app_version': '2.0',
            'device_id': 'cloudcare',
            'user_id': '51cd680c0bd1c21bb5e63dab99748248',
            'additional_filters': {'footprint': True},
            'domain': 'aspace',
            'host': 'http://localhost:8000',
            'user_data': {},
            'case_id_new_RegCase_0': '1c2e7c76f0c84eaea5b44bc7d1d3caf0',
            'app_id': '6a48b8838d06febeeabb28c8c9516ab6',
            'username': 'ben'
        }

        self.case = {
            'case_id': 'legolas',
            'properties': {
                'case_type': 'dragon',
                'case_name': 'rocky',
                'date_opened': None,
                'owner_id': 'ben-123',
            },
            'closed': False,
            'indices': {},
            'attachments': {},
        }

    def test_load_form_without_context(self):
        """
        This test is to ensure that load_form will correctly make an HTTP call when
        there is no form context for the case ids.
        """
        def mock_query(query_function, criteria):
            raise MockFunctionException
        touchcare.query_case_ids = mock_query

        try:
            xformplayer.load_form(
                self.xform,
                session_data=self.session_data,
            )
        except MockFunctionException:
            pass
        else:
            self.fail()

    def test_load_form_with_context(self):
        def mock_query(query_function, criteria):
            self.fail()
        touchcare.query_case_ids = mock_query

        xformplayer.load_form(
            self.xform,
            session_data=self.session_data,
            form_context={
                'all_case_ids': ['legolas', 'sauron'],
                'case_model': self.case
            }
        )


if __name__ == '__main__':
    unittest.main()
