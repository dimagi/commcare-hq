from unittest.mock import patch

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.const import ES_INDEX_TASK_HELPER_BASE_KEY
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.tasks import index_es_docs_with_location_props
from corehq.apps.geospatial.utils import get_celery_task_tracker


@es_test(requires=[case_search_adapter], setup_class=True)
class TestIndexESDocsWithLocationProps(TestCase):
    domain = 'test'
    gps_prop_name = 'gps-stuff'

    def setUp(self):
        super().setUp()
        factory = CaseFactory(self.domain)
        case_list = [
            _create_case(factory, self.gps_prop_name, name='foo'),
            _create_case(factory, self.gps_prop_name, name='bar'),
        ]
        case_search_adapter.bulk_index(case_list, refresh=True)
        self.celery_task_helper = get_celery_task_tracker(self.domain, ES_INDEX_TASK_HELPER_BASE_KEY)
        geo_config = GeoConfig.objects.create(
            domain=self.domain,
            case_location_property_name=self.gps_prop_name,
        )
        self.addCleanup(geo_config.delete)
        self.addCleanup(self.celery_task_helper.mark_completed)
        self.addCleanup(self.celery_task_helper.clear_progress)

    @patch('corehq.apps.geospatial.tasks.MAX_GEOSPATIAL_INDEX_DOC_LIMIT', 1)
    def test_max_doc_limit_reached(self):
        index_es_docs_with_location_props.apply(args=[self.domain])
        expected_output = {
            'status': 'ERROR',
            'progress': 0,
            'error_slug': 'TOO_MANY_CASES'
        }
        self.assertEqual(self.celery_task_helper.get_status(), expected_output)

    def test_index_docs(self):
        index_es_docs_with_location_props.apply(args=[self.domain])
        manager.index_refresh(case_search_adapter.index_name)

        doc_count = case_query_for_missing_geopoint_val(self.domain, self.gps_prop_name).count()
        self.assertEqual(doc_count, 0)
        expected_output = {
            'status': None,
            'progress': 100,
            'error_slug': None
        }
        self.assertEqual(self.celery_task_helper.get_status(), expected_output)


def _create_case(factory, gps_prop_name, name):
    return factory.create_case(
        case_name=name,
        case_type='fooey',
        update={gps_prop_name: '1.1 2.2'}
    )
