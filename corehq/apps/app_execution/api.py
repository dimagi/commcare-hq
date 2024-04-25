import copy
import dataclasses
import json
from enum import Enum
from functools import cached_property
from importlib import import_module
from io import StringIO

import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest

from corehq.apps.app_execution import const, data_model
from corehq.apps.app_execution.exceptions import AppExecutionError
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest
from dimagi.utils.web import get_url_base


class FormplayerException(Exception):
    pass


class BaseFormplayerClient:
    """Client class used to make requests to Formplayer"""

    def __init__(self, domain, username, user_id, formplayer_url=None):
        self.domain = domain
        self.username = username
        self.user_id = user_id
        self.formplayer_url = formplayer_url or get_formplayer_url()

    def __enter__(self):
        self.session = self._get_requests_session()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_requests_session(self):
        return requests.Session()

    def close(self):
        self.session.close()
        self.session = None

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


class LocalUserClient(BaseFormplayerClient):
    """Authenticates as a local user to Formplayer.

    This fakes a user login in the Django session and uses the session cookie to authenticate with Formplayer."""

    @cached_property
    def user(self):
        return User.objects.get(username=self.username)

    def _get_requests_session(self):
        session = requests.Session()

        engine = import_module(settings.SESSION_ENGINE)
        self.django_session = engine.SessionStore()

        # Create a fake request to store login details.
        request = HttpRequest()
        request.session = self.django_session
        login(request, self.user, "django.contrib.auth.backends.ModelBackend")
        # Save the session values.
        request.session.save()
        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        session.cookies.set(session_cookie, request.session.session_key)
        return session

    def close(self):
        super().close()
        request = HttpRequest()
        request.session = self.django_session
        request.user = self.user
        logout(request)
        self.django_session = None

    def _make_request(self, endpoint, data_bytes, headers):
        if 'XSRF-TOKEN' not in self.session.cookies:
            response = self.session.get(f"{self.formplayer_url}/serverup")
            response.raise_for_status()

        xsrf_token = self.session.cookies['XSRF-TOKEN']

        response = self.session.post(
            url=f"{self.formplayer_url}/{endpoint}",
            data=data_bytes,
            headers={
                "X-XSRF-TOKEN": xsrf_token,
                **headers
            },
        )
        response.raise_for_status()
        return response.json()


class UserPasswordClient(LocalUserClient):
    """Authenticates using a username and password.

    This client logs in to CommCareHQ and uses the session cookie to authenticate with Formplayer.
    You can use this client with a local or remote CommCareHQ + Formplayer instance.
    """
    def __init__(self, domain, username, user_id, password, commcare_url=None, formplayer_url=None):
        self.password = password
        self.commcare_url = commcare_url or get_url_base()
        super().__init__(domain, username, user_id, formplayer_url)

    def _get_requests_session(self):
        session = requests.Session()
        login_url = self.commcare_url + f"/a/{self.domain}/login/"
        session.get(login_url)  # csrf
        response = session.post(
            login_url,
            {
                "auth-username": self.username,
                "auth-password": self.password,
                "cloud_care_login_view-current_step": ['auth'],  # fake out two_factor ManagementForm
            },
            headers={
                "X-CSRFToken": session.cookies.get('csrftoken'),
                "REFERER": login_url,  # csrf requires this for secure requests
            },
        )
        assert (response.status_code == 200)
        return session


class HmacAuthClient(BaseFormplayerClient):
    """Authenticates using a shared secret key.

    Note: This client does not currently work for case search requests and form submissions."""

    def _make_request(self, endpoint, data_bytes, headers):
        response = self.session.post(
            url=f"{self.formplayer_url}/{endpoint}",
            data=data_bytes,
            headers={
                "X-MAC-DIGEST": get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data_bytes),
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
    form_mode: str = const.FORM_MODE_HUMAN
    sync_first: bool = False
    data: dict = None
    log: StringIO = dataclasses.field(default_factory=StringIO)

    def __enter__(self):
        self.client.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.__exit__(exc_type, exc_val, exc_tb)

    def clone(self):
        return dataclasses.replace(self, data=copy.deepcopy(self.data) if self.data else None)

    @cached_property
    def app_build_id(self):
        app = get_app(self.client.domain, self.app_id, latest=True)
        build_on = "Latest Version"
        if app.built_on:
            build_on = app.built_on.strftime("%B %d, %Y")
        print(f"Using app '{app.name}' ({app._id} - {build_on})", file=self.log)
        return app._id

    def sync(self):
        if not self.sync_first:
            return
        print(f"Syncing user data for {self.client.username}", file=self.log)
        sync_db(self.client.domain, self.client.username)

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

        if current_data.get("errors"):
            raise AppExecutionError(current_data["errors"])
        raise AppExecutionError(f"Unknown screen type: {current_data}")

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
            assert not step.is_form_step, step
        selections = list(self.data.get("selections", [])) if self.data else []
        data = {
            **self._get_base_data(),
            "app_id": self.app_build_id,
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
        assert step.is_form_step, step
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
        is_form_step = isinstance(step, (data_model.AnswerQuestionStep, data_model.SubmitFormStep))
        if is_form_step and self.form_mode == const.FORM_MODE_IGNORE:
            self.log_step(step, skipped=True)
            return
        if self.form_mode == const.FORM_MODE_NO_SUBMIT and isinstance(step, data_model.SubmitFormStep):
            self.log_step(step, skipped=True)
            return
        data = self.get_request_data(step) if step else self.get_session_start_data()
        self.data = self.client.make_request(data, self.request_url(step))
        self.log_step(step)

    def log_step(self, step, indent="  ", skipped=False):
        if not step:
            print("Starting app session:\n", file=self.log)
        skipped_log = " (ignored)" if skipped else ""
        print(f"Execute step: {step or 'START'} {skipped_log}", file=self.log)
        if skipped:
            return
        double_indent = indent * 2
        screen, data = self.get_screen_and_data()
        print(f"{indent}New Screen: {screen}", file=self.log)
        if data:
            if screen == ScreenType.START:
                print("", file=self.log)
            elif screen == ScreenType.MENU:
                for command in data:
                    print(f"{double_indent}Command: {command['displayText']}", file=self.log)
            elif screen == ScreenType.CASE_LIST:
                for row in data:
                    print(f"{double_indent}Case: {row['id']}", file=self.log)
            elif screen == ScreenType.SEARCH:
                for display in data:
                    print(f"{double_indent}Search field: {display['text']}", file=self.log)
            elif screen == ScreenType.FORM:
                for item in data:
                    if item["type"] == "question":
                        answer = item.get('answer', None) or '""'
                        print(f"{double_indent}Question: {item['caption']}={answer}", file=self.log)


def execute_workflow(session: FormplayerSession, workflow):
    with session:
        session.sync()
        execute_step(session, None)
        for step in workflow.steps:
            execute_step(session, step)


def execute_step(session, step):
    if step and (children := step.get_children()):
        for child in children:
            session.execute_step(child)
    else:
        session.execute_step(step)
