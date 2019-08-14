from __future__ import absolute_import, unicode_literals

import json
import traceback

import json_delta
import laboratory

from corehq.apps.userreports.models import (
    ReportComparisonDiff,
    ReportComparisonException,
    ReportComparisonTiming,
)
from corehq.util.json import CommCareJSONEncoder


class UCRExperiment(laboratory.Experiment):

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
        ReportComparisonException.objects.create(
            domain=self.context['domain'],
            control_report_config_id=self.context['report_config_id'],
            candidate_report_config_id=self.context['new_report_config_id'],
            filter_values=self.context['filter_values'],
            exception=formatted_exception,
        )

    def log_diff(self, control_value, candidate_value):
        # handle serialization of Decimals and dates
        control_value = json.loads(json.dumps(control_value, cls=CommCareJSONEncoder))
        candidate_value = json.loads(json.dumps(candidate_value, cls=CommCareJSONEncoder))

        diff = json_delta.diff(control_value, candidate_value, verbose=False)
        ReportComparisonDiff.objects.create(
            domain=self.context['domain'],
            control_report_config_id=self.context['report_config_id'],
            candidate_report_config_id=self.context['new_report_config_id'],
            filter_values=self.context['filter_values'],
            control=control_value,
            candidate=candidate_value,
            diff=diff,
        )

    def log_timing(self, control, candidate):
        ReportComparisonTiming.objects.create(
            domain=self.context['domain'],
            control_report_config_id=self.context['report_config_id'],
            candidate_report_config_id=self.context['new_report_config_id'],
            filter_values=self.context['filter_values'],
            control_duration=control.duration.total_seconds(),
            candidate_duration=candidate.duration.total_seconds(),
        )
