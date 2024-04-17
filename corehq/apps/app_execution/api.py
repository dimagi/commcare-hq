import copy
import dataclasses
import json
from enum import Enum

import requests

import settings
from corehq.apps.app_execution import data_model
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest
from dimagi.utils.web import get_url_base


class FormplayerException(Exception):
    pass


class BaseFormplayerClient:

    def __init__(self, domain, username, user_id, commcare_url=None, formplayer_url=None):
        self.domain = domain
        self.username = username
        self.user_id = user_id
        self.commcare_url = commcare_url or get_url_base()
        self.formplayer_url = formplayer_url or get_formplayer_url()

    def __enter__(self):
        self.session = requests.Session()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def make_request(self, data, endpoint):
        data_bytes = json.dumps(data).encode('utf-8')
        response_data = self._make_request(endpoint, data_bytes, headers={
            "Content-Type": "application/json",
            "content-length": str(len(data)),
            "X-FORMPLAYER-SESSION": self.user_id,
        })

        if response_data.get("exception") or response_data.get("status") == "error":
            raise FormplayerException(response_data.get("exception", "Unknown error"))
        return response_data

    def _make_request(self, endpoint, data_bytes, headers):
        raise NotImplementedError()


class UserFormplayerClient(BaseFormplayerClient):
    def __init__(self, domain, username, user_id, password, commcare_url=None, formplayer_url=None):
        self.password = password
        super().__init__(domain, username, user_id, commcare_url, formplayer_url)

    def __enter__(self):
        self.session = requests.Session()
        login_url = self.commcare_url + f"/a/{self.domain}/login/"
        self.session.get(login_url)  # csrf
        response = self.session.post(
            login_url,
            {
                "auth-username": self.username,
                "auth-password": self.password,
                "cloud_care_login_view-current_step": ['auth'],  # fake out two_factor ManagementForm
            },
            headers={
                "X-CSRFToken": self.session.cookies.get('csrftoken'),
                "REFERER": login_url,  # csrf requires this for secure requests
            },
        )
        assert (response.status_code == 200)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _make_request(self, endpoint, data, headers):
        if 'XSRF-TOKEN' not in self.session.cookies:
            response = self.session.get(f"{self.formplayer_url}/serverup")
            response.raise_for_status()

        xsrf_token = self.session.cookies['XSRF-TOKEN']

        response = self.session.post(
            url=f"{self.formplayer_url}/{endpoint}",
            data=data,
            headers={
                "X-XSRF-TOKEN": xsrf_token,
                **headers
            },
        )
        response.raise_for_status()
        return response.json()


class HmacFormplayerClient(BaseFormplayerClient):

    def _make_request(self, endpoint, data, headers):
        response = self.session.post(
            url=f"{self.formplayer_url}/{endpoint}",
            data=data,
            headers={
                "X-MAC-DIGEST": get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data),
                **headers
            },
        )
        response.raise_for_status()
        return response.json()


class ScreenType(str, Enum):
    START = "start"
    MENU = "menu"
    CASE_LIST = "case_list"
    DETAIL = "detail"
    SEARCH = "search"
    FORM = "form"


@dataclasses.dataclass
class FormplayerSession:
    client: BaseFormplayerClient
    app_id: str
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

        type_ = current_data.get("type")
        if type_ == "commands":
            return ScreenType.MENU, current_data["commands"]
        if type_ == "entities":
            return ScreenType.CASE_LIST, current_data["entities"]
        if type_ == "query":
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

    def request_url(self, step):
        screen = self.current_screen
        if screen == ScreenType.START:
            return "navigate_menu_start"
        if screen == ScreenType.FORM:
            return "submit-all" if isinstance(step, data_model.SubmitFormStep) else "answer"
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
            permitted_types = (data_model.CommandStep, data_model.EntitySelectStep, data_model.QueryStep)
            assert isinstance(step, permitted_types), step
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
            "query_data": self.data.get("query_data", {}) if self.data else {},
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
            "domain": self.client.domain,
            "restore_as": None,
            "tz_from_browser": "UTC",
            "tz_offset_millis": 0,
            "username": self.client.username,
        }

    def execute_step(self, step):
        data = self.get_request_data(step) if step else self.get_session_start_data()
        self.data = self.client.make_request(data, self.request_url(step))


def execute_workflow(session: FormplayerSession, workflow):
    execute_step(session, None)
    for step in workflow.steps:
        execute_step(session, step)


def execute_step(session, step):
    if step and (children := step.get_children()):
        for child in children:
            session.execute_step(child)
    else:
        session.execute_step(step)
