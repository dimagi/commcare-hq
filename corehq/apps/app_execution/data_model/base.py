from __future__ import annotations

import dataclasses

from attr import define

from . import steps


@define
class AppWorkflow:
    steps: list[steps.Step] = dataclasses.field(default_factory=list)

    def __jsonattrs_to_json__(self):
        return {
            "steps": [step.to_json() for step in self.steps]
        }

    @classmethod
    def __jsonattrs_from_json__(cls, data):
        return cls(steps=steps.steps_from_json(data["steps"]))

    def __str__(self):
        return " -> ".join(str(step) for step in self.steps)
