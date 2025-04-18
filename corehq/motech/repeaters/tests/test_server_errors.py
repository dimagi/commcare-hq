from collections import namedtuple
from unittest.mock import patch
from uuid import uuid4

import pytest
from requests.exceptions import ConnectionError
from unmagic import fixture, use

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.motech.models import ConnectionSettings

from ..const import State
from ..models import HTTP_STATUS_BACK_OFF, FormRepeater

ResponseMock = namedtuple('ResponseMock', 'status_code reason')


@use('db')
@fixture
def domain_obj_fixture():
    domain = 'repeater-backoff-tests'
    domain_obj = create_domain(domain)
    helper = DomainSubscriptionMixin()
    helper.setup_subscription(domain, SoftwarePlanEdition.PRO)
    try:
        yield domain_obj
    finally:
        helper.teardown_subscription(domain)
        domain_obj.delete()


@use(domain_obj_fixture)
@fixture
def repeater_fixture():
    domain_obj = domain_obj_fixture()
    url = 'https://www.example.com/api/'
    conn = ConnectionSettings.objects.create(
        domain=domain_obj.name,
        name=url,
        url=url,
    )
    repeater = FormRepeater.objects.create(
        domain=domain_obj.name,
        connection_settings_id=conn.id,
        include_app_id_param=False,
    )
    try:
        yield repeater
    finally:
        repeater.delete()
        conn.delete()


@use(repeater_fixture)
def test_success_on_200():
    repeater = repeater_fixture()
    resp = ResponseMock(status_code=200, reason='OK')
    with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
        simple_request.return_value = resp
        instance_id = submit_xform(repeater.domain)
    repeat_record = repeater.repeat_records.last()
    assert repeat_record.payload_id == instance_id
    assert repeat_record.attempts.last().state == State.Success
    assert repeat_record.next_check is None


@use(repeater_fixture)
@pytest.mark.parametrize("status_code, reason", [
    (status.value, status.description)
    for status in HTTP_STATUS_BACK_OFF
])
def test_backoff_on_status_code(status_code, reason):
    repeater = repeater_fixture()
    resp = ResponseMock(status_code=status_code, reason=reason)
    with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
        simple_request.return_value = resp
        instance_id = submit_xform(repeater.domain)
    repeat_record = repeater.repeat_records.last()
    assert repeat_record.payload_id == instance_id
    assert repeat_record.attempts.last().state == State.Fail
    assert repeat_record.next_check is not None


@use(repeater_fixture)
def test_backoff_on_connection_error():
    repeater = repeater_fixture()
    with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
        simple_request.side_effect = ConnectionError()
        instance_id = submit_xform(repeater.domain)
    repeat_record = repeater.repeat_records.last()
    assert repeat_record.payload_id == instance_id
    assert repeat_record.attempts.last().state == State.Fail
    assert repeat_record.next_check is not None


def submit_xform(domain):
    instance_id = str(uuid4())
    xform = f"""<?xml version='1.0' ?>
    <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
          xmlns="https://www.commcarehq.org/test/ServerErrorTests/">
        <foo/>
        <bar/>
        <meta>
            <deviceID>ServerErrorTests</deviceID>
            <timeStart>2011-10-01T15:25:18.404-04</timeStart>
            <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
            <username>admin</username>
            <userID>testy.mctestface</userID>
            <instanceID>{instance_id}</instanceID>
        </meta>
    </data>
    """
    submit_form_locally(xform, domain)
    return instance_id
