from .base import AppWorkflow
from . import steps
from . import expectations  # noqa

EXAMPLE_WORKFLOW = AppWorkflow(steps=[
    steps.CommandStep(value="My Module"),
    steps.EntitySelectStep(value="clinic_123"),
    steps.QueryStep(inputs={"name": "John Doe"}),
    steps.EntitySelectIndexStep(value=0),
    steps.FormStep(children=[
        steps.AnswerQuestionStep(question_text="Name", value="John Doe"),
        steps.AnswerQuestionStep(question_text="Age", value="30"),
        steps.SubmitFormStep(),
    ]),
])
