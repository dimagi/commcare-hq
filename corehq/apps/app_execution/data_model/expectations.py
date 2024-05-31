from typing import ClassVar

from attr import asdict, define

from corehq.apps.app_execution.exceptions import AppExecutionError
from submodules.xml2json import xml2json


@define
class Expectation:
    type: ClassVar[str]

    def evaluate(self, session):
        try:
            return self._evaluate(session)
        except Exception as e:
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


@define
class CasePresent(Expectation):
    type: ClassVar[str] = "case_present"
    xpath_filter: str

    def _evaluate(self, session):
        xpath = f"count(instance('casedb')/casedb/case[{self.xpath_filter}]) > 0"
        return evaluate_xpath(session, xpath) == "true"


@define
class CaseAbsent(Expectation):
    type: ClassVar[str] = "case_absent"
    xpath_filter: str

    def _evaluate(self, session):
        xpath = f"count(instance('casedb')/casedb/case[{self.xpath_filter}]) = 0"
        return evaluate_xpath(session, xpath) == "true"


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
        data["session_id"] = session["session_id"]
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
    type_ = raw_expectation.pop("type").replace("expect:", "")
    if type_ not in TYPE_MAP:
        raise ValueError(f"Unknown expectation type {type_}")
    return TYPE_MAP[type_].from_json(raw_expectation)
