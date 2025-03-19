from unittest.mock import patch, ANY

from ..models import SQLSislogBackend
from ...http import models as http_models
from ...http.tests.test_models import TestHttpBackend


class TestSQLSislogBackend(TestHttpBackend):
    backend_model = SQLSislogBackend

    @patch.object(http_models, 'urlopen')
    def test_sends_without_error(self, mock_urlopen):
        message = self._create_message(phone_number='1234567890', text='Hello World')
        backend = self._create_backend(url='http://www.dimagi.com')

        backend.send(message)
        mock_urlopen.assert_called_with(
            'http://www.dimagi.com?message=Hello+World&number=1234567890',
            context=ANY,
            timeout=ANY,
        )
