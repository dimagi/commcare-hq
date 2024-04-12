import dataclasses
from datetime import datetime
from itertools import chain

from . import data_model
from .api import FormplayerSession, ScreenType, execute_step


def discover_workflows(domain, app_id, user_id, username):
    """
    Returns a list of workflows for the given app_id and user_id
    """
    session = FormplayerSession(domain=domain, app_id=app_id, user_id=user_id, username=username)
    execute_step(session, None)
    explorations = [
        WorkflowExploration(workflow=data_model.Workflow(steps=[step]), session=session.clone())
        for step in get_branches(session)
    ]
    to_explore = explorations
    while to_explore:
        to_explore = list(chain.from_iterable(_expand_workflow(exploration) for exploration in to_explore))
        explorations.extend(to_explore)
    return [exploration.workflow for exploration in explorations]


def _expand_workflow(exploration):
    """Expand the current workflow to completion.
    This also returns a generator of newly discovered workflows to explore.
    """
    while not exploration.completed:
        exploration.execute_next_step()
        branches = get_branches(exploration.session)
        if not branches:
            exploration.completed = True
        else:
            if len(branches) > 1:
                yield from [exploration.extend(branch) for branch in branches[1:]]
            exploration.workflow.steps += [branches[0]]


def get_branches(session):
    screen, data = session.get_screen_and_data()
    if session.current_screen == ScreenType.START:
        return []
    elif session.current_screen == ScreenType.MENU:
        return [data_model.CommandStep(value=command["displayText"]) for command in data]
    elif session.current_screen == ScreenType.CASE_LIST:
        # select first one for now
        return [data_model.EntitySelectStep(value=data[0]["id"])]
    elif session.current_screen == ScreenType.SEARCH:
        pass  # TODO
    elif session.current_screen == ScreenType.DETAIL:
        pass
    elif session.current_screen == ScreenType.FORM:
        # no support for conditional questions
        return [data_model.FormStep(children=[
            data_model.AnswerQuestionStep(
                question_text=item["caption"],
                question_id=item["question_id"],
                value=_get_value_for_type(item)
            )
            for item in data if item["type"] == "question"
        ] + [data_model.SubmitFormStep()])]


def _get_value_for_type(item):
    if answer := item.get("answer"):
        return answer

    datatype = item["datatype"]
    if datatype == "str":
        return "some answer"
    if datatype == "date":
        return datetime.today().isoformat()
    if datatype == "select":
        return "1"  # first option in choice list


@dataclasses.dataclass
class WorkflowExploration:
    workflow: data_model.Workflow
    session: FormplayerSession
    completed: bool = False
    step_index: int = 0

    def execute_next_step(self):
        step = self.workflow.steps[self.step_index]
        execute_step(self.session, step)
        self.step_index += 1
        return self

    def extend(self, branch):
        new_steps = branch if isinstance(branch, list) else [branch]
        workflow = data_model.Workflow(steps=self.workflow.steps + new_steps)
        return WorkflowExploration(
            workflow=workflow,
            session=self.session.clone(),
            step_index=self.step_index
        )
