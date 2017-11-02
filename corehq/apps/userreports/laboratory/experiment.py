from __future__ import absolute_import
from __future__ import unicode_literals
import json
import logging
import traceback

from django.core.serializers.json import DjangoJSONEncoder
import json_delta
import laboratory

diff_logger = logging.getLogger('ucr_diff')
exception_logger = logging.getLogger('ucr_exception')
timing_logger = logging.getLogger('ucr_timing')


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
            if cmp(control_value, candidate_value) != 0:
                self.log_diff(control_value, candidate_value)

    def log_exception(self, control_value, candidate_exc):
        formatted_exception = traceback.format_exception(
            candidate_exc[0], candidate_exc[1], candidate_exc[2]
        )
        exception_logger.info(
            "",
            extra={
                'domain': self.context['domain'],
                'report_config_id': self.context['report_config_id'],
                'filter_values': self.context['filter_values'],
                'candidate': formatted_exception,
            })

    def log_diff(self, control_value, candidate_value):
        diff = json_delta.diff(control_value, candidate_value, verbose=False)
        diff_logger.info(
            "",
            extra={
                'domain': self.context['domain'],
                'report_config_id': self.context['report_config_id'],
                'filter_values': self.context['filter_values'],
                'control': json.dumps(control_value, cls=DjangoJSONEncoder),
                'diff': json.dumps(diff, cls=DjangoJSONEncoder)
            })

    def log_timing(self, control, candidate):
        timing_logger.info(
            "",
            extra={
                'domain': self.context['domain'],
                'report_config_id': self.context['report_config_id'],
                'filter_values': self.context['filter_values'],
                'control_duration': control.duration,
                'candidate_duration': candidate.duration
            })
