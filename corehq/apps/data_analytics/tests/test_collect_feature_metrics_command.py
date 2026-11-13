from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class TestCollectFeatureMetricsCommand(SimpleTestCase):

    @patch(
        'corehq.apps.data_analytics.management.commands'
        '.collect_feature_metrics._collect_feature_metrics_for_domain'
    )
    def test_processes_specified_domains(self, mock_collect):
        out = StringIO()
        call_command(
            'collect_feature_metrics', 'domain1', 'domain2',
            stdout=out,
        )
        assert mock_collect.call_count == 2
        mock_collect.assert_any_call('domain1')
        mock_collect.assert_any_call('domain2')
