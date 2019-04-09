from __future__ import absolute_import

import uuid

import attr
from django.test import SimpleTestCase

from corehq.util.global_context.api import global_context


@attr.s
class Request(object):
    domain = attr.ib()
    user = attr.ib(default=None)


@attr.s
class User(object):
    username = attr.ib()


class GlobalRequestTest(SimpleTestCase):

    def setUp(self):
        self.domain = 'domain:' + uuid.uuid4().hex
        self.username = 'user:' + uuid.uuid4().hex

    def tearDown(self):
        global_context.reset()
        super(GlobalRequestTest, self).tearDown()

    def test_get_domain_null(self):
        self.assertEqual(None, global_context.get_current_domain())

    def test_get_username_null(self):
        self.assertEqual(None, global_context.get_current_username())

    def test_get_username_null_on_request(self):
        global_context.request = Request(domain=self.domain)
        self.assertEqual(None, global_context.get_current_username())

    def test_get_domain_username(self):
        global_context.request = Request(domain=self.domain, user=User(username=self.username))
        self.assertEqual(self.domain, global_context.get_current_domain())
        self.assertEqual(self.username, global_context.get_current_username())

        global_context.current_domain = 'jack'
        global_context.current_username = 'jill'
        self.assertEqual('jack', global_context.get_current_domain())
        self.assertEqual('jill', global_context.get_current_username())

    def test_clear(self):
        request = Request(domain=self.domain)
        global_context.request = request
        global_context.current_domain = 'a'
        global_context.current_username = 'b'
        global_context.context_key = 'c'

        self.assertEqual(request, global_context.request)
        self.assertEqual('a', global_context.current_domain)
        self.assertEqual('b', global_context.current_username)
        self.assertEqual('c', global_context.context_key)

        global_context.reset()

        self.assertIsNone(global_context.request)
        self.assertIsNone(global_context.current_domain)
        self.assertIsNone(global_context.current_username)
        self.assertIsNone(global_context.context_key)
