import json

from corehq.apps.app_execution.data_model import AppWorkflow, steps
from corehq.apps.app_execution.api import ScreenType, get_screen_type
from corehq.apps.app_execution.models import AppWorkflowConfig

NON_FORM_ENDPOINTS = {"navigate_menu_start", "navigate_menu", "get_details"}
FORM_ENDPOINTS = {"answer", "submit-all"}
ENDPOINTS = NON_FORM_ENDPOINTS | FORM_ENDPOINTS


def parse_har_from_string(har_string):
    return HarParser().parse(json.loads(har_string))


class HarParser:
    def __init__(self):
        self.domain = None
        self.app_id = None
        self.steps = []
        self.current_screen = None
        self.screen_data = None
        self.form_step = None

    def parse(self, har_data):
        """
        Extracts a workflow from a HAR file and returns it as a dictionary.
        """
        for endpoint, entry in get_formplayer_entries(har_data['log']['entries']):
            if not self.current_screen and endpoint != 'navigate_menu_start':
                # Skip until we get the first navigate_menu_start
                continue

            request_data = json.loads(entry['request']['postData']['text'])
            response_data = json.loads(entry['response']['content']['text'])

            if endpoint in FORM_ENDPOINTS:
                self.set_form_step()
            else:
                self.clear_form_step()

            if endpoint == 'navigate_menu_start' or self.current_screen == ScreenType.START:
                if self.current_screen:
                    assert self.domain == request_data["domain"]
                    assert self.app_id == request_data["app_id"]
                else:
                    self.current_screen = ScreenType.START
                    self.domain = request_data["domain"]
                    self.app_id = request_data["app_id"]

            elif endpoint == 'navigate_menu':
                step = self._extract_navigation_step(request_data)
                if step:
                    self.steps.append(step)
            elif endpoint == 'answer':
                self.form_step.children.append(self._extract_form_answer_step(request_data))
            elif endpoint == 'submit-all':
                self.form_step.children.append(steps.SubmitFormStep())
            elif endpoint == 'get_details':
                # skip over detail screens and don't update current screen and screen data
                continue

            self.current_screen = get_screen_type(response_data)
            self.screen_data = response_data

        return AppWorkflowConfig(
            domain=self.domain, app_id=self.app_id, workflow=AppWorkflow(steps=self.steps)
        )

    def _extract_navigation_step(self, request_data):
        selections_changed = request_data.get("selections") != self.screen_data.get("selections")
        if self.current_screen == ScreenType.MENU:
            last_selection = _get_last_selection(request_data, int)
            command = self.screen_data["commands"][last_selection]["displayText"]
            return steps.CommandStep(value=command)
        elif self.current_screen == ScreenType.CASE_LIST:
            if selections_changed:
                return self._get_entity_select_step(request_data)
            elif self._get_query_data(request_data).get("inputs") is None:
                return steps.ClearQueryStep()
        elif self.current_screen == ScreenType.SEARCH:
            return self._get_search_step(request_data)
        elif self.current_screen == ScreenType.SPLIT_SEARCH:
            if not selections_changed:
                return self._get_search_step(request_data)
            else:
                return self._get_entity_select_step(request_data)

        elif self.current_screen == ScreenType.DETAIL:
            pass
        else:
            raise Exception(f"Unexpected screen type: {self.current_screen}")

    def _get_entity_select_step(self, request_data):
        last_selection = _get_last_selection(request_data)
        if is_action(last_selection):
            return steps.CommandIdStep(value=last_selection)
        elif is_multi_select(last_selection):
            return steps.MultipleEntitySelectStep(values=request_data["selectedValues"])
        else:
            return steps.EntitySelectStep(value=last_selection)

    def _get_search_step(self, request_data):
        query_data = self._get_query_data(request_data)
        if query_data and query_data["execute"]:
            return steps.QueryStep(inputs=query_data["inputs"])
        else:
            return steps.QueryInputValidationStep(inputs=query_data["inputs"])

    def _get_query_data(self, request_data):
        query_key = self.screen_data["queryKey"]
        query_data = request_data["query_data"].get(query_key)
        return query_data

    def _extract_form_answer_step(self, request_data):
        tree = self.screen_data["tree"]
        tree_item = [question for question in tree if question["ix"] == request_data["ix"]][0]
        step = steps.AnswerQuestionIdStep(
            question_id=tree_item["question_id"],
            value=request_data["answer"])
        return step

    def set_form_step(self):
        if not self.form_step:
            self.form_step = steps.FormStep(children=[])
            self.steps.append(self.form_step)

    def clear_form_step(self):
        self.form_step = None


def _get_last_selection(data, cast=None):
    selections = data["selections"]
    if not selections:
        return None
    selection = selections[-1]
    return cast(selection) if cast else selection


def is_action(selection):
    return selection.startswith("action")


def is_multi_select(selection):
    return selection == "use_selected_values"


def get_formplayer_entries(entries):
    base_url = None
    for entry in entries:
        request = entry['request']
        if request['method'] != 'POST':
            continue

        url = request['url']
        if not base_url:
            base_url = _get_formplayer_base_url(url)

        if not base_url:
            continue

        endpoint = url.removeprefix(base_url)
        yield endpoint, entry


def _get_formplayer_base_url(url):
    endpoint = url.split("/")[-1]
    if endpoint not in ENDPOINTS:
        return None
    return "/".join(url.split("/")[:-1]) + "/"
