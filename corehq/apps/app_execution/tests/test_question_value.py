from unittest.mock import Mock

from testil import eq

from corehq.apps.app_execution.data_model.expectations import get_question_value_from_tree, \
    get_question_value_from_xml


def test_get_question_value_from_tree():
    answer, found = get_question_value_from_tree("/data/nested/group/list_q_2", [
        {"binding": "/data/question1", "answer": None},
        {"binding": "/data/nested", "children": [
            {"binding": "/data/nested/group", "children": [
                {"binding": "/data/nested/group/list_q_2", "answer": "123"}
            ]}
        ]},
    ])
    eq(found, True)
    eq(answer, "123")


def test_get_question_value_from_tree_not_found():
    answer, found = get_question_value_from_tree("/data/nested/group/list_q_2", [])
    eq(found, False)
    eq(answer, None)


def test_get_question_value_from_xml():
    answer, found = get_question_value_from_xml(_get_session(), "/data/nested/group/list_q_2")
    eq(found, True)
    eq(answer, "123")


def test_get_question_value_from_xml_not_found():
    answer, found = get_question_value_from_xml(_get_session(), "/data/nested/group/list_q_3")
    eq(found, False)
    eq(answer, None)


def test_get_question_value_from_xml_repeat():
    answer, found = get_question_value_from_xml(_get_session(), "/data/repeat[2]/q1")
    eq(found, True)
    eq(answer, "def")


FORM_XML = """<data>
    <nested><group><list_q_2>123</list_q_2></group></nested>
    <repeat><q1>abc</q1></repeat>
    <repeat><q1>def</q1></repeat>
    <repeat><q1>ghi</q1></repeat>
</data>"""


def _get_session():
    return Mock(data={
        "instanceXml": {"output": FORM_XML}
    })
