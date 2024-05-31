from __future__ import annotations

import dataclasses

from attr import define

from . import steps as step_models  # noqa
from . import expectations


@define
class AppWorkflow:
    steps: list[step_models.Step | expectations.Expectation] = dataclasses.field(default_factory=list)

    def __jsonattrs_to_json__(self):
        return {
            "steps": [step.to_json() for step in self.steps]
        }

    @classmethod
    def __jsonattrs_from_json__(cls, data):
        return cls(steps=steps_from_json(data["steps"]))

    def __str__(self):
        return " -> ".join(str(step) for step in self.steps)


def steps_from_json(json_steps):
    steps = []
    for raw_step in json_steps:
        if raw_step["type"].startswith("expect:"):
            steps.append(expectations.expectation_from_json(raw_step))
        else:
            steps.extend(step_models.steps_from_json([raw_step]))
    return steps
