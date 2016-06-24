from django.test import SimpleTestCase
from mock import patch
from corehq.util.view_utils import json_error


class NotifyExceptionTest(SimpleTestCase):

    def test_notify_exception(self):
        err = ValueError('Bad value')

        @json_error
        def my_view(request):
            raise err

        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo')
            notify_exception_patch.assert_called_with('foo', 'JSON exception response: {}'.format(err))
