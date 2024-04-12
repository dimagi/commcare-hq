import copy
import dataclasses
import json
from enum import Enum

import requests

import settings
from corehq.apps.app_execution import data_model
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest


class FormplayerException(Exception):
    pass


class ScreenType(str, Enum):
    START = "start"
    MENU = "menu"
    CASE_LIST = "case_list"
    DETAIL = "detail"
    SEARCH = "search"
    FORM = "form"


@dataclasses.dataclass
class FormplayerSession:
    domain: str
    user_id: str
    username: str
    app_id: str
    session_id: str = None
    data: dict = None

    def clone(self):
        return dataclasses.replace(self, data=copy.deepcopy(self.data) if self.data else None)

    @property
    def current_screen(self):
        return self.get_screen_and_data()[0]

    def get_screen_and_data(self):
        return self._get_screen_and_data(self.data)

    def _get_screen_and_data(self, current_data):
        if not current_data:
            return ScreenType.START, None
        data = current_data.get("commands")
        if data:
            return ScreenType.MENU, data
        data = current_data.get("entities")
        if data:
            return ScreenType.CASE_LIST, data
        if current_data.get("type") == "query":
            return ScreenType.SEARCH, current_data.get("displays")
        data = current_data.get("details")
        if data:
            return ScreenType.DETAIL, data
        data = current_data.get("tree")
        if data:
            return ScreenType.FORM, data
        if current_data.get("submitResponseMessage"):
            return self._get_screen_and_data(current_data["nextScreen"])

        raise ValueError(f"Unknown screen type: {current_data}")

    @property
    def request_url(self):
        screen = self.current_screen
        if screen == ScreenType.START:
            return "navigate_menu_start"
        if screen == ScreenType.FORM:
            return "answer"
        return "navigate_menu"

    def get_session_start_data(self):
        return self._get_navigation_data(None)

    def get_request_data(self, step):
        if self.current_screen != ScreenType.FORM:
            return self._get_navigation_data(step)
        else:
            return self._get_form_data(step)

    def _get_navigation_data(self, step):
        if step:
            assert isinstance(step, (data_model.CommandStep, data_model.EntitySelectStep)), step
        selections = list(self.data.get("selections", [])) if self.data else []
        data = {
            **self._get_base_data(),
            "app_id": self.app_id,
            "locale": "en",
            "geo_location": None,
            "cases_per_page": 10,
            "preview": False,
            "offset": 0,
            "selections": selections,
            "query_data": {},
            "search_text": None,
            "sortIndex": None,
        }
        return step.get_request_data(self, data) if step else data

    def _get_form_data(self, step):
        assert isinstance(step, (data_model.AnswerQuestionStep, data_model.SubmitFormStep)), step
        data = {
            **self._get_base_data(),
            "debuggerEnabled": False,
        }
        return step.get_request_data(self, data)

    def _get_base_data(self):
        return {
            "domain": self.domain,
            "restore_as": None,
            "tz_from_browser": "UTC",
            "tz_offset_millis": 0,
            "username": self.username,
        }


def execute_workflow(session: FormplayerSession, steps):
    execute_step(session, None)
    for step in steps:
        execute_step(session, step)


def execute_step(session, step):
    if step and (children := step.get_children()):
        for child in children:
            _execute_leaf_step(session, child)
    else:
        _execute_leaf_step(session, step)


def _execute_leaf_step(session, step):
    print(f"Executing {step} from screen {session.data}")
    data = session.get_request_data(step) if step else session.get_session_start_data()
    print(f"Executing {step} with data: {data}")
    session.data = _make_request(session, data)
    print(f"--> Result: {session.data}")


def _make_request(session, data):
    data_bytes = json.dumps(data).encode('utf-8')
    response = requests.post(
        url=f"{get_formplayer_url()}/{session.request_url}",
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "content-length": str(len(data_bytes)),
            "X-MAC-DIGEST": get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data_bytes),
            "X-FORMPLAYER-SESSION": session.user_id,
        },
    )
    response.raise_for_status()
    data = response.json()
    if data.get("exception"):
        raise FormplayerException(data["exception"])
    return data
