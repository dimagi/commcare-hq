# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from mock import patch
from corehq.util.view_utils import json_error


@json_error
def my_view(request, err):
    raise err


class NotifyExceptionTest(SimpleTestCase):

    def test_notify_exception_utf8(self):
        err = ValueError('βªđ ṿåƚŭę'.encode('utf-8'))
        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo', err)
            notify_exception_patch.assert_called_with('foo', 'JSON exception response: βªđ ṿåƚŭę'.encode('utf-8'))

    def test_notify_exception_unicode(self):
        err = ValueError('βªđ ṿåƚŭę')
        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo', err)
            notify_exception_patch.assert_called_with('foo', 'JSON exception response: βªđ ṿåƚŭę'.encode('utf-8'))
