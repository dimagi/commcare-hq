from __future__ import absolute_import, unicode_literals

import json
import traceback

import json_delta
import laboratory

from corehq.util.json import CommCareJSONEncoder
from custom.icds_reports.models.util import (
    CitusDashboardDiff,
    CitusDashboardException,
    CitusDashboardTiming,
)


class DashboardQueryExperiment(laboratory.Experiment):

    def publish(self, result):
        control = result.control
        candidate = result.observations[0]

        control_value = control.value
        try:
            candidate_value = candidate.value
        except AttributeError:
            self.log_exception(control_value, candidate.exc_info)
        else:
            self.log_timing(control, candidate)
            if control_value != candidate_value:
                self.log_diff(control_value, candidate_value)

    def log_exception(self, control_value, candidate_exc):
        formatted_exception = traceback.format_exception(
            candidate_exc[0], candidate_exc[1], candidate_exc[2]
        )
        CitusDashboardException.objects.create(
            data_source=self.context['data_source'],
            context=self.context,
            exception=formatted_exception
        )

    def log_diff(self, control_value, candidate_value):
        # handle serialization of Decimals and dates
        control_value = json.loads(json.dumps(control_value, cls=CommCareJSONEncoder))
        candidate_value = json.loads(json.dumps(candidate_value, cls=CommCareJSONEncoder))

        diff = json_delta.diff(control_value, candidate_value, verbose=False)
        CitusDashboardDiff.objects.create(
            data_source=self.context['data_source'],
            context=self.context,
            control=control_value,
            candidate=candidate_value,
            diff=diff
        )

    def log_timing(self, control, candidate):
        CitusDashboardTiming.objects.create(
            data_source=self.context['data_source'],
            context=self.context,
            control_duration=control.duration.total_seconds(),
            candidate_duration=candidate.duration.total_seconds()
        )
