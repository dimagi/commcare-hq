import pytest

from unittest.mock import Mock

from corehq.motech.repeaters.models import ConnectFormRepeater
from corehq.motech.repeaters.repeater_generators import CONNECT_XMLNS, ConnectFormRepeaterPayloadGenerator

FORM_META = {
    "@xmlns": "http://openrosa.org/jr/xforms",
    "appVersion": "Formplayer Version: 2.53",
    "app_build_version": 53,
    "commcare_version": None,
    "deviceID": "Formplayer",
    "instanceID": "f469597c-7587-4029-ba9d-215ce7660674",
    "timeEnd": "2023-06-07T12:34:11.718000Z",
    "timeStart": "2023-06-07T12:34:10.178000Z",
    "userID": "66da891a459b2781c28bf2e0c50cbe67",
    "username": "test",
    "location": "20.090209 40.09320 20 40",
}

DELIVER_JSON = {
    "deliver": {
        "@xmlns": CONNECT_XMLNS,
        "@id": 5,
        "name": "deliver_unit_1",
        "entity_id": "person_1",
        "entity_name": "Person 1",
    }
}

MOCK_FORM = {
    "app_id": "0c0a8beabdc4b83bc84fd457f2b047a2",
    "archived": False,
    "build_id": "2614cb25dbf44ed29527164281e8b7dd",
    "domain": "ccc-test",
    "form": {
        "#type": "data",
        "@name": "Form Name",
        "@uiVersion": "1",
        "@version": "53",
        "meta": FORM_META,
        "question_path": "answer",
        "connect_path": DELIVER_JSON
    },
    "id": "f469597c-7587-4029-ba9d-215ce7660674",
    "metadata": FORM_META,
    "received_on": "2023-06-07T12:34:12.153323Z",
    "server_modified_on": "2023-06-07T12:34:12.509392Z",
    "attachments": {
        "form.xml": {
            "content_type": "text/xml",
            "length": 1000,
            "url": "https://www.commcarehq.org/form.xml",
        }
    },
}


def test_connect_repeater():
    repeater = ConnectFormRepeater(domain="test")
    generator = ConnectFormRepeaterPayloadGenerator(repeater)
    form = Mock()
    form.to_json = Mock(return_value=MOCK_FORM)
    payload = generator.get_payload(None, form)
    assert payload["metadata"] == FORM_META
    assert payload["form.connect_path.deliver"] == DELIVER_JSON["deliver"]
    with pytest.raises(KeyError):
        payload["form"]
