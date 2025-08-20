import copy
import logging
import re
from typing import ClassVar

from attr import asdict, define

from corehq.apps.app_execution.exceptions import AppExecutionError
from submodules.xml2json import xml2json
from jsonpath_ng.ext import parse as jsonpath_parse

log = logging.getLogger(__name__)


@define
class Expectation:
    type: ClassVar[str]

    def get_children(self):
        """Compatibility with Step.get_children()"""
        return []

    def evaluate(self, session):
        try:
            return self._evaluate(session)
        except Exception as e:
            log.exception(f"Error evaluating expectation {self}")
            raise AppExecutionError(f"Error evaluating expectation {self}") from e

    def _evaluate(self, session):
        raise NotImplementedError()

    def to_json(self):
        return {"type": f"expect:{self.type}", **asdict(self)}

    @classmethod
    def from_json(cls, data):
        return cls(**data)


@define
class XpathExpectation(Expectation):
    type: ClassVar[str] = "xpath"
    xpath: str

    def _evaluate(self, session):
        return evaluate_xpath(session, self.xpath) == "true"

    def __str__(self):
        return f"{self.type}({self.xpath})"


@define
class CasePresent(Expectation):
    type: ClassVar[str] = "case_present"
    xpath_filter: str

    def _evaluate(self, session):
        xpath = f"count(instance('casedb')/casedb/case[{self.xpath_filter}]) > 0"
        return evaluate_xpath(session, xpath) == "true"

    def __str__(self):
        return f"{self.type}({self.xpath_filter})"


@define
class CaseAbsent(Expectation):
    type: ClassVar[str] = "case_absent"
    xpath_filter: str

    def _evaluate(self, session):
        xpath = f"count(instance('casedb')/casedb/case[{self.xpath_filter}]) = 0"
        return evaluate_xpath(session, xpath) == "true"

    def __str__(self):
        return f"{self.type}({self.xpath_filter})"


@define
class QuestionValue(Expectation):
    type: ClassVar[str] = "question_value"
    question_path: str
    value: str

    def _evaluate(self, session):
        from corehq.apps.app_execution.api import ScreenType
        if not session.current_screen == ScreenType.FORM:
            session.log("QuestionValue expectation only works in form screens")
            return False

        result, found = get_question_value_from_tree(self.question_path, session.data.get("tree", []))
        if not found:
            result, found = get_question_value_from_xml(session, self.question_path)

        if found:
            return result == self.value

        session.log(f"Question {self.question_path} not found")
        return False

    def __str__(self):
        return f"{self.type}({self.question_path} = {self.value})"


def get_question_value_from_tree(question_id, tree):
    for node in tree:
        if node.get("binding") == question_id:
            return node.get("answer"), True
        if node.get("children"):
            result, found = get_question_value_from_tree(question_id, node.get("children"))
            if found:
                return result, True
    return None, False


def get_question_value_from_xml(session, question_id):
    xml = session.data.get("instanceXml", {}).get("output")
    if not xml:
        session.log("No form instance XML found")
        return None, False

    try:
        name, json_response = xml2json.xml2json(xml.encode())
    except xml2json.XMLSyntaxError:
        session.log("Unable to parse form instance XML")
        return None, False
    return _get_question_value_from_json(session, question_id, {name: json_response})


def _get_question_value_from_json(session, question_id, json_response):
    expr = question_id.replace("/", ".")
    expr = _convert_to_zero_index(expr)
    try:
        jsonpath_expr = jsonpath_parse(f"$.{expr}")
    except Exception:
        session.log(f"Unable to parse the question path {question_id}")
        return None, False

    values = [match.value for match in jsonpath_expr.find(json_response)]
    if values:
        return values[0], True

    return None, False


def _convert_to_zero_index(expr):
    """Xpath is 1-indexed but jsonpath is 0-indexed"""
    for index in re.findall(r"\[(\d+)]", expr):
        expr = expr.replace(f"[{index}]", f"[{int(index) - 1}]")
    return expr


def evaluate_xpath(session, xpath):
    data = _get_data(session, xpath)
    url = _get_url(session.current_screen)
    data = session.client.make_request(data, url)
    return _get_result(session, data)


def _get_data(session, xpath):
    from corehq.apps.app_execution.api import ScreenType
    data = {
        **session.get_base_data(),
        "app_id": session.app_build_id,
        "selections": session.data.get("selections", []),
        "query_data": session.data.get("query_data", {}),
        "xpath": xpath,
        "debugOutput": "basic"
    }
    if session.current_screen == ScreenType.FORM:
        data["session_id"] = session.data["session_id"]
    return data


def _get_result(session, response):
    output = response.get("output")
    if response.get("status") == "validation-error":
        session.log(f"Xpath validation error: {output}")
        return

    if not output:
        return

    try:
        _, json_response = xml2json.xml2json(output.encode())
    except xml2json.XMLSyntaxError:
        session.log(f"Unable to parse result {output}")
        return

    return json_response


def _get_url(screen):
    from corehq.apps.app_execution.api import ScreenType
    if screen == ScreenType.FORM:
        return "evaluate-xpath"
    return "evaluate-menu-xpath"


TYPE_MAP = {step.type: step for step in Expectation.__subclasses__()}


def expectation_from_json(raw_expectation):
    raw_expectation = copy.deepcopy(raw_expectation)
    type_ = raw_expectation.pop("type").replace("expect:", "")
    if type_ not in TYPE_MAP:
        raise ValueError(f"Unknown expectation type {type_}")
    return TYPE_MAP[type_].from_json(raw_expectation)
