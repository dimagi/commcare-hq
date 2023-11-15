import doctest
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseBlock

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.geospatial.es import find_precision, get_max_doc_count
from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test-domain'


def fake_get_max_doc_count(query, case_property, precision):
    """Returns an int that looks a little like a doc count"""
    x = 12 - precision
    return 2 * x + 9_983


def test_find_precision():
    with patch(
        'corehq.apps.geospatial.es.get_max_doc_count',
        fake_get_max_doc_count,
    ):
        precision = find_precision(query=object(), case_property='foo')
        assert_equal(precision, 4)


@es_test(requires=[case_search_adapter], setup_class=True)
class TestGetMaxDocCount(TestCase):
    """
    Verify ``get_max_doc_count()`` using an example pulled from
    Elasticsearch docs.

    For more context, see
    https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html#_simple_low_precision_request
    and https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html#_high_precision_requests
    """  # noqa: E501

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with flag_enabled('GEOSPATIAL'):
            case_search_es_setup(DOMAIN, cls._get_case_blocks())

    @staticmethod
    def _get_case_blocks():
        case_blocks = []
        for name, coordinates in (
            ('NEMO Science Museum', '4.912350 52.374081'),
            ('Museum Het Rembrandthuis', '4.901618 52.369219'),
            ('Nederlands Scheepvaartmuseum', '4.914722 52.371667'),
            ('Letterenhuis', '4.405200, 51.222900'),
            ('Musée du Louvre', '2.336389 48.861111'),
            ("Musée d'Orsay", '2.327000 48.860000'),
        ):
            case_blocks.append(CaseBlock(
                case_id=str(uuid4()),
                case_type='museum',
                case_name=name,
                update={
                    GPS_POINT_CASE_PROPERTY: coordinates,
                },
                create=True,
            ))
        return case_blocks

    def test_max_doc_count(self):
        query = CaseSearchES().domain(DOMAIN)
        case_property = get_geo_case_property(DOMAIN)
        precision = 3
        max_doc_count = get_max_doc_count(query, case_property, precision)
        self.assertEqual(max_doc_count, 3)


def test_doctests():
    import corehq.apps.geospatial.es as module

    results = doctest.testmod(module)
    assert results.failed == 0
