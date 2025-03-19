from unittest.mock import Mock

from testil import eq

from corehq.apps.app_execution.api import FormplayerSession, ScreenType
from corehq.apps.app_execution.data_model.expectations import XpathExpectation, _get_result

RESULT_XML = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><result>{}</result>"


def test_expect_xpath_true():
    result = _test_expect_xpath("true")
    eq(result, True)


def test_expect_xpath_false():
    result = _test_expect_xpath("anything else")
    eq(result, False)


def _test_expect_xpath(result):
    session = Mock(
        current_screen=ScreenType.FORM,
        app_build_id="123",
        data={"selections": ["0"], "session_id": "123"},
        client=Mock(),
        spec=FormplayerSession,
    )
    session.get_base_data.return_value = {}
    session.client.make_request.return_value = {"output": RESULT_XML.format(result)}
    expectation = XpathExpectation(xpath="1 = 2")
    return expectation.evaluate(session)


def test_expect_xpath_get_result():
    response = {"output": RESULT_XML.format("<session>test</session>")}
    result = _get_result(Mock(log=_raise_log), response=response)
    eq(result, {"session": "test"})


def test_expect_xpath_get_result_error():
    response = {"output": RESULT_XML.format("<bad xml>")}
    logs = []
    result = _get_result(Mock(log=_collect_log(logs)), response=response)
    eq(result, None)
    eq(logs, [f"Unable to parse result {response['output']}"])


def _raise_log(x):
    raise Exception(x)


def _collect_log(logs):
    def log(x):
        logs.append(x)

    return log
