from django.test import SimpleTestCase
from corehq.apps.reports.standard.deployments import _get_histogram_aggregation_for_app


class TestGetHistogramAggregationForApp(SimpleTestCase):

    def test_get_histogram_aggregation_for_app(self):
        expected_output = {
            "nested": {
                "path": "reporting_metadata.test_field"
            },
            "aggs": {
                "filtered_agg": {
                    "filter": {
                        "term": {
                            "reporting_metadata.test_field.app_id": "123"
                        }
                    },
                    "aggs": {
                        "date_histogram": {
                            "date_histogram": {
                                "field": "reporting_metadata.test_field.test_date",
                                "interval": "day",
                                "format": "yyyy-MM-dd",
                                "min_doc_count": 1
                            }
                        }
                    }
                }
            }
        }

        aggs = _get_histogram_aggregation_for_app('test_field', 'test_date', '123')
        self.assertEqual(expected_output, aggs.assemble())
