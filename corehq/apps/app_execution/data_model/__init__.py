from .base import AppWorkflow
from . import steps

EXAMPLE_WORKFLOW = AppWorkflow(steps=[
    steps.CommandStep(value="My Module"),
    steps.EntitySelectStep(value="clinic_123"),
    steps.QueryStep(inputs={"name": "John Doe"}),
    steps.EntitySelectIndexStep(value=0),
    steps.FormStep(children=[
        steps.AnswerQuestionStep(question_text="Name", question_id="name", value="John Doe"),
        steps.AnswerQuestionStep(question_text="Age", question_id="age", value="30"),
        steps.SubmitFormStep(),
    ]),
])
