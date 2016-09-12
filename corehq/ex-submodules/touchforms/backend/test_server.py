import unittest
import sys
from xcp import InvalidRequestException
import xformserver
import xformplayer


class DummyServer(xformserver.XFormHTTPGateway):
    def __init__(self):
        pass


class XFormServerTest(unittest.TestCase):

    def setUp(self):
        self.server = DummyServer()

    def test_param_no_session_id(self):
        content = {
            'action': xformplayer.Actions.ADD_REPEAT
        }
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('session' in e.message)
        else:
            self.fail()

    def test_param_no_answer(self):
        content = {
            'action': xformplayer.Actions.ANSWER,
            'session-id': '123'
        }
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('answer' in e.message)
        else:
            self.fail()

    def test_param_no_action(self):
        content = {}
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('All actions' in e.message)
        else:
            self.fail()

    def test_unrecognized_action(self):
        content = {
            'action': 'nonexistant',
            'session-id': '123'
        }
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('action' in e.message)
        else:
            self.fail()

    def test_touchcare_filter_params(self):
        content = {
            'action': 'touchcare-filter-cases',
            'filter_expr': 'something',
        }
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('hq_auth' in e.message)
        else:
            self.fail(str(e))

        content = {
            'action': 'touchcare-filter-cases',
            'hq_auth': {},
        }
        try:
            xformserver.handle_request(content, self.server)
        except InvalidRequestException, e:
            self.assertTrue('filter_expr' in e.message)
        else:
            self.fail(str(e))

if __name__ == '__main__':
    unittest.main()
