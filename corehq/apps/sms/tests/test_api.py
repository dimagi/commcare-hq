import pytest

from corehq.apps.sms.api import get_connect_error_code
from corehq.apps.sms.mixin import BackendProcessingException
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.users.models import ConnectIDUserLink


@pytest.mark.parametrize('error, expected_code', [
    (
        BackendProcessingException('HTTP 400: {"error": "invalid channel"}'),
        MessagingEvent.ERROR_CONNECT_GATEWAY,
    ),
    (
        ConnectIDUserLink.DoesNotExist(),
        MessagingEvent.ERROR_CONNECT_USER_NOT_FOUND,
    ),
    (
        AttributeError("'NoneType' object has no attribute 'get_django_user'"),
        MessagingEvent.ERROR_INTERNAL_SERVER_ERROR,
    ),
])
def test_get_connect_error_code(error, expected_code):
    assert get_connect_error_code(error) == expected_code
