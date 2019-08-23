# coding=utf-8

import six
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
            if six.PY3:
                notify_exception_patch.assert_called_with(
                    'foo',
                    "JSON exception response: "
                    "b'\\xce\\xb2\\xc2\\xaa\\xc4\\x91 \\xe1\\xb9\\xbf\\xc3\\xa5\\xc6\\x9a\\xc5\\xad\\xc4\\x99'"
                )
            else:
                notify_exception_patch.assert_called_with(
                    'foo',
                    "JSON exception response: βªđ ṿåƚŭę"
                )


    def test_notify_exception_unicode(self):
        err = ValueError('βªđ ṿåƚŭę')
        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo', err)
            notify_exception_patch.assert_called_with('foo', 'JSON exception response: βªđ ṿåƚŭę')
