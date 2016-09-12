import os
import unittest
import xformplayer

CUR_DIR = os.path.dirname(__file__)


class GUIStub(object):
    def __getattr__(self, name):
        return lambda _self: None


class GlobalStateManagerTest(unittest.TestCase):

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

        self.session_metadata = {
            'extensions': [],
            'session_data': self.session_data,
            'nav_mode': 'fao',
            'api_auth': {},
            'staleness_window': 1,
            'form_context': {
                'all_case_ids': ['legolas', 'sauron'],
                'case_model': self.case
            }
        }

        xformplayer._init()
        self.manager = xformplayer.GlobalStateManager.get_globalstate()

    def test_basic_sessions(self):

        xform_session = xformplayer.XFormSession(
            self.xform,
            instance=None,
            **self.session_metadata
        )
        self.manager.cache_session(xform_session)

        cached = self.manager.get_session(xform_session.uuid)

        self.assertEqual(cached.uuid, xform_session.uuid)

    def test_instance_state(self):
        """
        This test ensures that the xform state properly gets updated after answering a question and adding a
        repeat group
        """
        name = 'Harry Potter'
        original_name = 'rocky'
        xform_session = xformplayer.XFormSession(
            self.xform,
            instance=None,
            **self.session_metadata
        )
        self.manager.cache_session(xform_session)

        tree = xform_session.response({
            'session_id': xform_session.uuid,
        })
        self.assertEqual(tree['tree'][0]['answer'], original_name)

        # Answer first question which is a text question
        xformplayer.answer_question(xform_session.uuid, name, '0')

        cached = self.manager.get_session(xform_session.uuid)
        cached_tree = cached.response({
            'session_id': xform_session.uuid,
        })
        self.assertEqual(cached_tree['tree'][0]['answer'], name)
        self.assertEqual(cached.uuid, xform_session.uuid)

if __name__ == '__main__':
    unittest.main()
