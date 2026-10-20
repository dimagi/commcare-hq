from unittest.mock import Mock, patch

import pytest

from corehq.apps.sms.api import get_connect_error_code, send_connect_message
from corehq.apps.sms.mixin import BackendProcessingException
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.users.models import ConnectIDUserLink


@pytest.mark.parametrize('error, expected_code', [
    (
        BackendProcessingException('HTTP 400: CHANNEL_DOES_NOT_EXIST'),
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


@pytest.mark.parametrize('error, notified', [
    (BackendProcessingException('HTTP 400'), False),
    (ConnectIDUserLink.DoesNotExist(), False),
    (AttributeError('boom'), True),
])
def test_send_connect_message_only_notifies_internal_errors(error, notified):
    backend = Mock()
    backend.send.side_effect = error
    with patch('corehq.apps.sms.api.log_sms_exception') as log_sms_exception:
        assert send_connect_message(Mock(), backend) is False
    assert log_sms_exception.called == notified
